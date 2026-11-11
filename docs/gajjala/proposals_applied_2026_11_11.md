# 🧠 The entries proposals, applied — armed-only 🧠, one ring per name, chase facts, 💧, 🌅, 🔝 (2026-11-11)

**#1 and #2 REDUCE how many 🧠 pushes ring** — a tightening, by his word. Everything else is words / display only: no
gate, threshold, A+ rule, lane rule or order changed. UNMEASURED — no proposal here has a measured edge; #5–#7 are
pre-registered studies, not run.

## His words

- Ajay 2026-11-11 ~08:28 ET: *"Also apply your proposal too."*
- "your proposal" = the 9-row table "Proposals — every one is HIS CALL" in
  `/Users/ajay/clinet-test/eod-audits/research/2026-11-11_entries_followthrough.md`. Built: #1, #2, #3 (additive only),
  #4, #8, #9. #5 / #6 / #7 are studies → pre-registration only.

## 1. Proposal #1 — a 🧠 rings only when ARMED

`GC.POTENTIAL_PUSH_ARMED_ONLY = True`. In `potential.run_pass`, a potential that cleared every other gate while still
BUILDING (`kind != POTENTIAL_KINDS[0]`) is held `BUILDING_HELD` "building" (`HELD_WORDS["building"]` "building — rings
once when the trigger arms") and counted `building_held`. `potential.eligible`: a doc held ONLY "building" (no other
reason ever written) passes and rings the first time it arms — no continuity test (a re-armed structure is the event);
while it is still building it is re-held (idempotent, one list entry) and counted again on each pass. A doc that ALSO
carries a rule / add / store hold keeps that reason's own test. The board still lists building AND armed.

## 2. Proposal #2 — one 🧠 ring per name per session

`GC.POTENTIAL_ONE_RING_PER_NAME = True`. `run_pass` builds `rang` = every symbol of today's docs that has a `push` block
(any setup; claimed / pushed / no_target / failed / shadow — fail closed). A potential of a name in `rang` is held
`NAME_HELD` "name_rang" (`HELD_WORDS["name_rang"]` "this name already rang today — one 🧠 ring per name") and counted
`name_held`; `eligible` returns False for it for the rest of the day. After a claim — or a claim another pass already
holds — the symbol joins `rang`, so a second setup of one name in the same pass is held (the first in `order_key` order
rings: armed first, then volume). Per page (each page its own store). A ⚡ break record (`brk`) never counts here.

**The pass order** (the reason chain, first match wins): join → `closed_day` → window (`muted` / `outside_hours`) →
`stale_tape` → the 📌 / 🎪 add hold (GG's floor) → **`name_rang` (#2)** → **`building` (#1)**. Both new checks run LAST,
so the existing counters keep their meaning (a building first sighting inside his first `NO_TRADE_AFTER_OPEN_MIN`
minutes is still held and counted `muted`, and still needs the unbroken path to ring when it arms).

Counters: `potential.COUNT_KEYS` gains `building_held` and `name_held`, appended after `trader_held`.

Words (honesty — the ring rule changed): `potential.ring_rule()` builds the sentence from the two switches ("the first
time it is armed (every rule met, only the break missing) — one push per name and session"; both off → the old words,
byte for byte); GG5 `push_note`, the ℹ️ Rules line, the GG1 `variant.WORDS_1M["push_potential"]` sentence and the 🧠
toggle's detail on /notifications say so. `/alerts` prints the two new held words (Alerts.tsx `GG_POTENTIAL_HELD_ROW`).
Both proposals apply to both pages (one engine).

**The GG5 WRITES golden moves** (`backend/tests/fixtures/gajjala/gg5_writes_2026_10_27.json`,
`test_gajjala_variant_gg5_identity.py`): the pass doc's `potential` counts gain the two new counters `building_held` /
`name_held`. The same regen carries the behaviour of #1 / #2 (a building claim becomes a "building" hold; a later-armed
fixture doc may write a new armed claim; a second setup of one name may become a "name_rang" hold) and the tracker
`last.session_volume` the ⚡ break watch reads (docs/gajjala/entry_break_2026_11_11.md). Regenerated once in the shared
tail, verified key for key, dated in the test's docstring. The 11-10 lesson: "a wording ask moves the WRITES golden: ask
first" — his "apply your proposal" covers the behaviour; the regen itself was not put to him.

## 3. Proposal #3 — chase facts on the 1-minute A+ push (additive)

`alerts.chase_text(trigger, stop, last_px)` → ONE clause right after the stop bit of the A+ body, on the **1-minute page
ONLY** (`v is V.GG1`): `CHASE_TEXT` "last {px} · {pct} vs the trigger · {r}R left to +{m}R", or `CHASE_PAST_TEXT` "…
already past +{m}R" once the last price is at or over GG's target (`GC.LEDGER_R_MULT`, R from `ledger.plan_of`).
`last_px` = the pass ctx `price` (the latest closed 1-minute close). Facts only: no threshold, no verdict word, no gate.
**The push still rings** exactly as before (`GAJJALA_1M_PUSH_MODE` and the `gajjala_1m_setup` toggle untouched). **Never
on 🚩 (GG5) or 🧪 (GGA)** — their bytes do not move. No clause on a missing / non-finite / zero last price or a no-risk
plan.

## 4. Proposal #4 — 💧 volume-dried marker

`tab.vol_dried_text(read)` → `chips.vol_dried` = `tab.VOL_DRIED_TEXT` "💧 volume dried up" when the read's own criteria
row `detectors.K3_VOL_KEY` is met AND the read is live (`detectors.LIVE_STATES`); else the key is absent. An indicator:
no order, no gate, no push. FE pill `data-testid="gg-vol-dried-{SYM}"`, text verbatim.

## 5. Proposal #8 — 🌅 Day 2 on the ☀️ pre-market sub

`tab.day2_block` → `day2` on GG5's ☀️ sub only. **A list, no push.** Rows: (a) yesterday's A+ that RANG LIVE (one row per
symbol = its earliest ring, the first-ring-counts rule), by ring time — `DAY2_APLUS_TEXT`; then (b) yesterday's
after-hours carry names not already in (a) — `DAY2_CARRY_TEXT`; each + `DAY2_LISTED_TEXT` " · on today's list" when the
name is listed today. Title `DAY2_TITLE`, note `DAY2_NOTE`, empty `DAY2_EMPTY`. **Tri-state:** an unknown entries read
OR an unknown carry (a read fault, or no after-hours pass wrote yesterday's doc) → `None`, nothing printed — never "No
A+ rang" on a read that failed. FE `data-testid="gg-day2"`.

## 6. Proposal #9 — 🔝 Focus

`tab.focus_block(tiles, order_flags)` on GG5's five setup subs and the 🧠 sub, AFTER `broker_bottom`. **Display only** —
never reorders, drops or gates a card. The first `GC.FOCUS_N` cards of the served order whose symbol is NOT on his 🚫
list (`order_flags`, read for every viewer — same rows for every reader) get `tile.focus = True`, and `focus` = {n, text:
`tab.FOCUS_TEXT`} is served ONLY when the board has more than `FOCUS_N` cards AND exactly `FOCUS_N` unflagged cards are
picked (fewer — his 🚫 names fill the rest → no header, no mark). FE: the header above the first card
(`gg-focus-head`) and a divider after the last focus card (`gg-focus-divider`); every card still listed.

## 7. Proposals #5 / #6 / #7 — pre-registered, NOT run

`backend/tests/fixtures/gajjala/entries_followups_prereg_2026_11_11.md`, frozen before any script or number: #5 GG-style
exits, #6 a wider stop, #7 🎾 "dipped under the base, then broke". Variants from GG's own rules; out-of-sample splits,
placebo, CI. Runs after 16:00 ET only, read-only. Nothing built in the lane. A positive read is a HIS CALL for a paper
variant — never a gate.

## What did NOT change

The GG5 and 🧪 A+ push bytes; every gate and threshold (`K11_MIN_SESSION_VOLUME`, the window, the detectors); the paper
lane and its orders; `OWNER_KEEP_SET`; the 🧠 board's listing and order (`POT_ORDER_TEXT`); the push toggles; the crontab.

## Tests

`backend/tests/test_gajjala_potential_armed_name_2026_11_11.py` (#1 / #2: the chain order, the counters, the
`eligible()` table, a still-building re-hold, the tracker's `session_volume` contract; NEGATIVES: a muted building doc
keeps the unbroken test, `name_rang` is final, switches off → old behaviour and old words, the 1-minute tracker bytes
unchanged). `test_gajjala_1m_chase_facts_2026_11_11.py` (#3; NEGATIVES: GG5 bytes never move, never GGA, bad last
price / no-risk plan → no clause, the 1-minute mode untouched). `test_gajjala_card_plan_focus_day2_2026_11_11.py` T2–T4
(#4 / #9 / #8; NEGATIVES on each: not-live read, ≤ `FOCUS_N` cards, 🚫 names, unknown reads, never a push). Re-pinned
(dated): `COUNT_KEYS` tail in `test_gajjala_trader_names_2026_10_27.py` / `test_gajjala_promo_names_2026_10_29.py`, the
GG1 sentence in `test_gajjala_variant_2026_10_27.py`, `test_gajjala_potential.py`. FE:
`GajjalaBoard.entry_2026_11_11.test.tsx`, `Alerts.test.tsx` (the two held words), `Notifications.gajjala_potential.test.tsx`.

## HIS CALL (not decided here)

1. **Chase clause on 🧪 too?** Built: the 1-minute page only. Say the word and the 🧪 Audited A+ carries it.
2. **🌅 " · on today's list"** is almost always true (the stay-listed rule keeps yesterday's names listed). Drop the
   clause, or test "qualified today" instead?
3. **Focus size.** Built `GC.FOCUS_N = 5` (his proposal's word; GG U14 "4–5 active, 1–2 in poor markets" — the
   poor-market size is not applied). Keep 5, 4, or a market-state switch.
