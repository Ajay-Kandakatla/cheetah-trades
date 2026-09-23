# 💎 Capital-quality upgrade alert (`capital_quality_upgrade`)

**Ajay, 2026-09-22:** *"Filter and have alerts and new look out for such
companies where whcih have very high quality."*

**Status: SHIPS OFF.** Registered everywhere a kind must be registered, muted
until he flips it at `/notifications`. Nothing in this package changed a
notification preference.

**NOT MEASURED.** `growth/capital_quality.py` ships `MEASURED = False` and its
`MEASURED_NOTE` rides on every push body, read from that module rather than
retyped. Nobody has measured whether a balance sheet improving predicts anything
on his universe. This is a screen, not an edge.

---

## Where it lives

| Path | What |
|---|---|
| `backend/growth/quality_alerts.py` | the module — the rule, the message, the pass |
| `backend/growth/__main__.py` | `python -m growth quality [--dry-run]` |
| `backend/tests/test_quality_alerts.py` | 58 tests, most of them negatives |
| `backend/push/subs.py` | `default_prefs()` — **`False`**; NOT in `OWNER_KEEP_SET` |
| `backend/market_hours/gate.py` | `MARKET_ALERT_KINDS` — closed days stay quiet |
| `backend/push/recent.py` | `DIGEST_KINDS` — the digest body is a list of names |
| `backend/supply_demand/alert_status.py` | `DAILY_PASS_KINDS` + `schedule_map()` |
| `backend/supply_demand/rules_info.py` | the ℹ️ Rules panel line |
| `frontend/src/lib/alertKinds.ts` | 💎 emoji + label for the bell / feed / chips |
| `frontend/src/hooks/useNotificationPrefs.ts` | the typed pref key |
| `frontend/src/pages/Notifications.tsx` | the toggle and what it explains |
| `frontend/src/pages/Alerts.tsx` | the daily-pass row on `/alerts` |
| `frontend/src/pages/Notifications.capital_quality.test.tsx` | 9 FE tests |

State: Mongo collection **`capital_quality_state`**, two `_id` namespaces —
`state|SYM` (the last observed verdicts + fiscal quarter) and
`claim|SYM|PERIOD` (the per-quarter latch). No TTL on either.

---

## THE CRON LINE — for the main session to install

`backend/crontab` is off limits to this package, and **a main deploy does not
ship a crontab change** (the cron container bind-mounts the HOST tree). Install
this by hand, verify in-container, then restart the cron container.

Place it immediately after the ✨ board-arrivals block (`backend/crontab`, the
line `8      8     *    *    1-5  … sepa.board_arrival growth`):

```
# ── 💎 Capital-quality upgrade push (growth/quality_alerts.py, 2026-09-22) ───
# Ajay 2026-09-22: "Filter and have alerts and new look out for such companies
# where whcih have very high quality."
# Fires ONLY on a definitional balance-sheet component crossing FAIL -> PASS on
# a NEW fiscal quarter. Once per (symbol, quarter), ever; 4 ring individually
# then one digest. The kind SHIPS OFF in push.subs.default_prefs — this line is
# a no-op for his phone until he turns it on at /notifications.
# 17:52 — after the 17:45 `sepa.board_metrics warm` that writes the balance
#         sheet this reads, and after the 17:50 `growth earnings` refresh.
52     17    *    *    1-5  /usr/local/bin/python -m market_hours.gate growth quality >> /var/log/cron.log 2>&1
```

Verify in-container, read-only, before installing:

```
docker exec -i -w /app cheetah-market-app-cron-1 /usr/local/bin/python -m growth quality --dry-run
```

A dry run performs **no** write — no claim, no send, no state record — but the
state READ is unconditional, so it reports a quarter already rung as seen rather
than as fresh.

---

## The rule

A **DEFINITIONAL** component of `growth/capital_quality.py` crosses
**FAIL → PASS** on a **NEW FISCAL QUARTER**.

| Component | The crossing, in his words |
|---|---|
| `net_cash` | now holds more cash than debt |
| `positive_fcf` | now throws off cash instead of burning it |
| `no_dilution` | share count stopped rising |
| `positive_roce` | return on capital turned positive |

Every one is a sign test or an inequality between two filed figures. **No
threshold is compared against a constant anybody chose**, here or in the read.
`UPGRADE_PHRASE`'s keys are pinned equal to `capital_quality`'s definitional
component keys by test, so a new leg over there cannot reach his phone as a raw
key.

### Why this is the trigger, and what was rejected

| Candidate | Verdict | Why |
|---|---|---|
| **(a)** a name ARRIVING on the 🚀 board that already grades high | **REJECTED** | Already a shipped kind — `sepa/board_arrival.py` (`board_arrival`, in `OWNER_KEEP_SET` since 2026-09-20) rings on exactly this event, so a second kind would buzz twice for one arrival. And the event barely happens: **measured 2026-09-22**, `growth_seen` holds 30 docs, **29 of them stamped 2026-09-12** (the ledger's own first cohort) and **zero arrivals in the ten days since**; `board_arrival_state` holds only its `__meta__` baseline — no name claimed, **nothing pushed** in the two days it has been live. The board rebuilds **Sundays**. Filtering a ~0-per-week event by quality yields an alert that never fires. |
| **(b)** a component FLIPS on a fresh filing | **ACCEPTED** | The one real event in the set. |
| **(c)** a high-grade name arriving at a demand band | **REJECTED** | `growth/alerts.py` (`growth_demand_alert`, keep-set, **9 pushes in 30 days**) already fires on that touch, already carries the room / proximity / floor-held gates, already prints the growth figures. A quality-filtered copy is a second buzz for one touch. Putting the grade *on that existing body* is his-call #5. |
| **(d)** a weekly digest of the current list | **REJECTED** | Zero turnover in ten days. The digest would restate the same ~21 names every week forever. That is the phone crying wolf; the 🚀 tab already is that list. |

### Four things that deliberately never fire

1. **`UNKNOWN → PASS`.** That is the app learning, not the company improving.
   The loudest instance is already scheduled: **0 of 485** `board_metrics`
   documents carry `capital_returns` today, so both RELATIVE components answer
   `insufficient_peers` for every name. The first warm cron with WP-1's code
   flips them for ~15 of 21 names **at once**, on a day when no business
   changed anywhere. A grade-word trigger would send fifteen pushes for it.
2. **The RELATIVE components, at all.** `roce_above_sector` /
   `capex_below_sector` can move because a **peer** filed. "Your company
   improved" must never be said because somebody else got worse.
3. **`PASS → FAIL`.** He asked for a look-out, not a sell signal. See his-call
   #2.
4. **The same quarter twice.** Two independent latches: the stored `period`
   (a same-quarter re-read never reaches the crossing test) and the permanent
   `claim|SYM|PERIOD` doc. This is the 🔔 price-alert lesson paid in advance —
   that kind re-fired **2,022 times**, every one `sent=0`, because a state with
   no latch re-asserts itself every pass.

A **first observation** of a symbol records a baseline and sends nothing — the
rule `sepa/board_arrival.tracking_since` applies to a board's first cohort, for
the same reason. A failed state READ is treated as "everything is a baseline",
i.e. **silence**: the opposite failure side from `growth.alerts._seen`, because
there a lost read costs a duplicate and here it would cost a false claim that a
company improved.

---

## RULE #7 — the as-of period, and why this is silent on day one

The quarter is read from **`capital_period`** — the fiscal quarter the BALANCE
SHEET figures came from, stamped by `sepa/board_metrics._attach_capital_returns`.
**There is no fallback.** The board row also carries a `period`, but that is the
INCOME-STATEMENT quarter the 100/100 screen ran on; using it as the as-of of a
balance-sheet fact would report a date that is not the date the figure came from.

A row with no `capital_period` is recorded and never pushed, counted as
`no_capital_period`. **Measured 2026-09-22: that is every row**, because no
`board_metrics` document carries `capital_returns` yet.

> **This kind is silent until the `board_metrics` warm cron next runs with
> WP-1's code.** One cron away, self-healing, and counted by name on `/alerts`
> rather than looking like a dead job. Silent-and-correct beats firing on a
> proxy date.

**The pass AFTER that one is a baseline too, and that is the fix for the one
real hole in this rule.** A record stored with `period: None` is not a
comparable prior: the observation it holds may belong to the SAME fiscal quarter
that later becomes readable. Before the fix, the first pass with a readable
`capital_period` compared today's verdicts against a period-less record and rang

```
💎 MU — now holds more cash than debt
… on FY2026 Q2 (was an earlier quarter) …
```

with **no filing behind it** — the same warm that made the period readable also
re-fetched cash / debt / shares. The `same_period` latch cannot catch it
(`"" != "FY2026 Q2"`). A record with no as-of quarter is now a **baseline**, so
the first readable pass records and rings nothing, and the NEXT genuine filing
compares normally. Pinned by
`test_NEGATIVE_a_stored_record_with_NO_PERIOD_is_a_baseline_never_a_prior` and
`test_a_period_less_baseline_still_rings_on_the_NEXT_real_quarter`.

Earnings for this board cluster: **16 of 21 rows share FY2026 Q2**. Expect the
kind to be near-silent for ~10 weeks and then bursty over ~3 weeks of earnings
season. The digest past `MAX_INDIVIDUAL` (imported from `growth.alerts`, not
retyped) absorbs the burst.

---

## What gates it: NOTHING

His standing rule (`alert_gates.room_gate` / `demand_proximity_gate`,
2026-09-05: *"Need only alerts on stocks that have atleast 5% to Supply and also
<1% bounce from demand zone"*) is scoped to pushes that name a **price** at a
**zone**. This push names neither — it reports a filing. Applying a room gate
would silently convert a fundamentals notice into an entry signal.
`sepa/board_arrival.py`, the closest precedent and also a board-level event,
applies no gate for the same reason and says so in its own comments.

**So no gate covers this kind.** No gate was invented for it. Whether a
fundamentals-driven push should carry one at all is **his-call #1**.

The pass summary deliberately carries **none** of
`skipped_room / skipped_proximity / skipped_direction / skipped_knife /
skipped_mood / skipped_floor`: `Alerts.tsx` sums those six names over every
recorded pass, and a counter borrowing one would silently pollute the S/D gate
aggregate on `/alerts`. Pinned by test.

---

## Counters on `/alerts`

`rows · graded · ungraded · no_capital_period · baseline · same_period ·
no_upgrade · upgraded · individual · digest · claimed_elsewhere ·
retry_pending · measured`

Each names its own reason, so a legitimately quiet evening reads as
silent-with-a-reason rather than as a stalled cron.

---

## This alert is also the app's only history of these figures

`board_metrics` keeps **one document per symbol and overwrites it** — there is
no per-quarter series of cash / debt / FCF / share count anywhere in this app.
That is why the flip rate could not be measured before shipping, and it is
stated rather than estimated. `capital_quality_state` is the first such history;
a study of whether a balance-sheet upgrade predicts anything becomes possible
once it has quarters in it. Until then `MEASURED` stays False.

---

## His-call items

1. **Should a fundamentals push carry a gate at all?** Nothing gates this kind
   today. The zone gates do not apply by their own terms. Options: leave it
   ungated (current), require the name to also be `enterable`, or require some
   minimum room. Ungated was chosen because it is the only option that does not
   invent a rule; the others are all his to pick.
2. **The deterioration side.** `PASS → FAIL` — it went net-debt, FCF turned
   negative, it started diluting — never fires. He asked for a look-out, not a
   sell signal, but a balance sheet going the other way on a name he holds is
   arguably the more valuable push. Same module, one line, his word.
3. **The slot.** 17:52 ET weekdays, chosen to sit after the 17:45 balance-sheet
   warm. A morning slot (with the ✨ 08:08 arrival pass) would batch the
   evening's filings into one waking-hours buzz instead.
4. **Re-arming a quarter.** The claim is permanent per `(symbol, quarter)`. If a
   send is muted (pref off) the sender reports "nobody targeted", which is
   terminal — so a quarter that flipped while the kind was OFF is **never
   replayed** when he turns it on. Deliberate (a replay would announce old news
   as new), but reversible if he would rather be caught up on switch-on.
5. **Put the grade on the 🚀 `growth_demand_alert` body instead of / as well.**
   That push already fires when a board name reaches demand; adding "3 of 4
   quality checks" to it is one clause and no new kind. Not done here because it
   changes an alert he already receives (Rule #10 caution), and it is cheap
   either way.
6. **A name can flip a component twice in different quarters** and ring both
   times — e.g. net-cash → net-debt → net-cash across three filings. Both are
   real events, so both ring. If he would rather hear each component once ever,
   that is a one-line change to the claim key.
