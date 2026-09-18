# 🎯 Un-hide by reason — a toggle for every word the hidden line prints

**2026-09-17.** Companion to [`enterable.md`](enterable.md), which owns the read
itself. This file owns only the **view filter** built on top of it.

---

## 1. The ask, verbatim

> Can you give me a toggle for the room too?
>
> I am not seeing all stocks on the selected filter due to this now

Sent with a screenshot of the Chart Maps **AMD** tab. Under the LEDGER overlay
row the count line read:

```
4 hidden (2 room < 5% · 1 floor swept · 1 no band) · show all
```

with one surviving tile (QNST, `🎯 WATCH · weak day`, `AMD raided · today`).

Standing context he had already given, the same morning, on the AMD work:

> Ignore the room thing.. Lot of time it will push though it.

That is about **room not removing names from his view**. It is not an
instruction to drop room from the push gate, and it is not a request to delete
the room reason from the board. Both sentences point the same way: room must
stop **hiding** things from him.

---

## 2. What shipped

Every reason the count line already printed is now a **button**. Click one and
the rows blocked **only** for that reason come back; click it again and they go.

| state | the line reads |
|---|---|
| nothing un-hidden | `40 hidden (19 room < 5% · 9 not at band · 8 no band · 2 floor broken · 2 floor swept) · show all` |
| `?unhide=room` | `21 hidden (✓ room < 5% · 9 not at band · 8 no band · 2 floor broken · 2 floor swept) · 19 un-hidden · show all` |
| `?unhide=proximity,room` | `12 hidden (✓ room < 5% · ✓ not at band · 8 no band · 2 floor broken · 2 floor swept) · 28 un-hidden · show all` |
| every code un-hidden | `0 hidden (✓ … ) · 40 un-hidden · show all` |
| filter OFF (`?show=all`) with two un-hidden | `showing all · 2 reasons un-hidden · enterable only` |
| `kind === 'n/a'` | `no demand read for this tab · filter off` — no chips, the toggles are inert |

`✓ <label>` is the un-hidden state; `N <label>` is the hiding state. The `·`
separator, the parentheses, the `show all` button and the
`· N without a read (shown last)` clause are unchanged. `un-hidden` and
`N reasons un-hidden` are the only new words on the line.

**Why a chip per reason and not the one room toggle he literally asked for.**
His sentence is "I am not seeing all stocks". Measured on his own tab (§3):
un-hiding room alone leaves **21 of 40 names still hidden**.

---

## 3. Measured on his payload, the morning he asked

Read-only, live, 2026-09-17:

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" \
  'http://127.0.0.1:8000/chart-maps?tab=amd&limit=40'
```

→ 200, 40 tiles, `enterable_kind = demand`, **40 of 40 BLOCKED**. Labels 1:1
with codes, zero length mismatches. The response is committed as the test
fixture `frontend/src/pages/__fixtures__/chart_maps_amd_2026_09_17.json` (bars
trimmed to the last 20 for size; nothing else touched), and
`ChartMapsReasonToggle.test.tsx` computes every expectation from it rather than
from a typed number.

| base code | rows carrying it | reason-set | rows |
|---|---|---|---|
| room | 25 | `{room}` | **19** |
| proximity | 9 | `{proximity, room}` | **6** |
| no_band | 8 | `{no_band}` | 8 |
| floor_swept | 2 | `{proximity}` | 3 |
| floor_broken | 2 | `{floor_swept}` / `{floor_broken}` | 2 / 2 |

Rows recovered by un-hiding:

| un-hidden set | rows shown |
|---|---|
| `room` alone | **19 of 40** |
| `room + proximity` | 28 |
| `room + proximity + no_band` | 36 |
| all five codes | 40 |

**This feature measures nothing and claims nothing.** It changes which rows are
drawn. No study, no CI, no placebo is owed, and none is implied on the page.

---

## 4. The rules, pinned

1. **The ignore set is a set of SERVED reason codes**, per view. Default empty =
   today's board, byte for byte.
2. **Shown** iff `mode === 'all'` **OR** `verdict !== 'BLOCKED'` **OR** (the row
   has ≥ 1 block reason, **every** one carries a served label, **and every one of
   their codes is in the ignore set**).
3. **A row blocked for two reasons needs both clicked.** Six rows on his AMD tab
   are blocked for `proximity` *and* `room`; un-hiding `room` alone leaves them
   hidden, because otherwise the line would lie about what he is looking at.
4. **An unknown read is never hidden and never un-hidden.** No read, a null
   verdict, a `BLOCKED` row with no reasons, a block reason the backend sent no
   label for, or a `reason_short` array **shorter** than `reasons` — all of them
   stay in the `unread` bucket or stay hidden, counted under
   `UNLABELLED_REASON = 'blocked'` and rendered as plain text with no button.
   Un-hiding is always explicit, never silent.
5. **Attribution of a still-hidden row** is its **first block reason whose code
   is not in the ignore set and which the backend labelled**. With an empty
   ignore set that is identical to the rule the line has used since 2026-09-15,
   so the shared mirror fixture pin keeps passing untouched.
6. **Chip ORDER is ignore-independent**: `baseline` desc, then label asc, then
   code asc, where `baseline` = the rows attributed to that code with an **empty**
   ignore set. Two properties, both required: at an empty ignore set the printed
   number *is* `baseline`, so the line is byte-identical to today; and `baseline`
   never moves when he clicks, so chips never reshuffle under his cursor.
7. **Re-attribution is real and it looks like a bug.** Un-hiding a code moves its
   multi-reason rows into the next un-ignored bucket, so another chip's printed
   number can grow, and the line can read non-monotonically after a click. That
   is correct: the number is "rows this reason is still holding back", not "rows
   carrying this reason". On his AMD payload nothing re-buckets when `room` is
   un-hidden, because `grade()` appends `proximity` **before** `room`
   (`enterable.py:2581-2589`) — the six `{proximity,room}` rows were always
   counted under `not at band`. A payload that orders codes the other way will
   show it.
8. **One chip per SERVED code, not per base code.** `floor_swept` and
   `floor_broken` both base-code to `floor`, but `REASON_SHORT["floor"]` is
   state-specific, so one grouped chip would need a joined label nobody served.
   A new floor state the sweep read invents gets its own chip and stays hidden
   until he clicks it — fail-closed.
9. **Un-hidden rows keep the SERVED order**, in place, still wearing their
   `⛔ <reason_short>` chip. `enterableChipText` is untouched.

---

## 5. The two controls both called "room"

| | ROOM FLOOR (2026-09-05) | UN-HIDE room (2026-09-17) |
|---|---|---|
| URL | `?room=any` | `?unhide=room` |
| Where it runs | **server**, `drop_low_room` against the live print | **browser**, over rows already served |
| What it touches | which tiles the API returns | which served tiles are drawn |
| Tabs | `ROOM_TABS` = `zones`, `deep_demand`, `quick_bounce`, `breaking` | every tab with `enterable_kind !== 'n/a'` |
| On the AMD tab | **does not exist** (`amd ∉ ROOM_TABS`) | this is the only room control there |

**They compose in one direction only.** The server drops first; the browser can
only un-hide what was served. On the four `ROOM_TABS` tabs, seeing every
room-blocked name needs **both** `any room` **and** the `room < 5%` chip. The
room chip's tooltip says so on those tabs, built from the served
`min_room_default` — never a typed 5.

---

## 6. What this does NOT change

Nothing in this change touches a rule, a gate, a threshold, a constant or a
default. Specifically, and each with the file that enforces it:

| path | file:line | still true |
|---|---|---|
| the phone, 🧲 demand | `backend/supply_demand/demand_alerts.py` (`EN.assess` runs LAST, after every gate) | a `room`-blocked row is not pushed; `skipped_not_enterable` counts it |
| the phone + paper lane, 🚀/🧲 zone edge | `backend/supply_demand/zone_edge.py:947,1006` | no push, no entry |
| the phone, 🪃 reversal | `backend/supply_demand/zone_bounce_alerts.py:544-546` | no push |
| the phone, 🚀 growth | `backend/growth/alerts.py` | no push |
| the grader | `backend/supply_demand/enterable.py::grade` | unchanged |
| the room gate | `alert_gates.ALERT_MIN_ROOM_PCT` | unchanged |
| the floor gate | `alert_gates.FLOOR_HELD_STATES` | unchanged |
| what BLOCKED means | `premarket_entry.GRADE_BLOCKED` | unchanged |

There is **no backend counterpart to the ignore set, by design** — a view
preference that could reach a gate is not a view preference.
`backend/tests/test_enterable_view_only_2026_09_17.py` carries a source guard
that fails if the tokens `unhide` / `ignore_reasons` / `ignore_set` ever appear
under `backend/supply_demand/`, plus three regression pins that force a
`reasons=["room"]` BLOCKED read through the demand, zone-edge and reversal push
paths and assert `sent == []`, `pushed == 0`, `skipped_not_enterable == 1`.

**The tile `limit` is still the other half of "all stocks".** The count line's
tooltip already says the count is over the tiles on the page. Un-hiding does not
reach further down the scan; raising `limit` does.

---

## 7. Where it lives

| piece | file |
|---|---|
| the rule | `frontend/src/lib/enterable.ts` — `IgnoreSet`, `blockReasons`, `isShown`, `partitionEnterable`, `mergeReasonStats` |
| the shared state | `frontend/src/hooks/useEnterableFilter.tsx` — `ignoreReasons`, `toggleReason` |
| the URL | `frontend/src/lib/chartMaps.ts` — `UNHIDE_PARAM`, `parseUnhide` (fails **closed**), `unhideParam` |
| the line | `frontend/src/components/HiddenCount.tsx` |
| the checkbox | `frontend/src/components/EnterableOnlyToggle.tsx` |
| the page | `frontend/src/pages/ChartMaps.tsx` |

The state lives in the URL and **nowhere else** — no `localStorage`. A filter he
cannot see the state of is a filter that quietly eats a board tomorrow, which is
the same reason `?show=all` was put there on 2026-09-15.

---

## 8. His call, still open

1. Should `enterable only` being re-checked **clear** `?unhide=`? It does not
   today — the OFF line names the count instead and preserves his selection.
2. Should un-hidden rows **sink below** the enterable ones? They sit in served
   order today.
3. Should `?unhide=` be **per tab** rather than one sticky set for the page?
4. Should the AMD tab also get the **server-side `any room` floor** (add `amd`
   to `ROOM_TABS`)? That needs the AMD builder to honour `min_room` — a backend
   change, and not what was hiding his names.
5. If what he actually wants is "stop grading room at all on the boards", that
   is a **rule change** and needs his explicit yes. It is not in this change.
