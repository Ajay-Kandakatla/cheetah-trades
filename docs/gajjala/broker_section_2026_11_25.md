# 🚫 A section header above the 🚫 cards on 🧠 Potential (2026-11-25) — backend

Ajay, 2026-11-25 ~10:25 ET, verbatim (his whole message, two lines):

> On the potential page move the no fidelity to the bottom segmented category.,
>
> Show me only EMBC

## What was built — in one line

**A header was added above the 🚫 cards. Nothing moved** — those cards have sat last on every card board since
2026-11-09 (`tab.broker_bottom`). **The 📈 Track rows and the 👀 line are untouched** (still interleaved). No gate, rule,
threshold, push, count, order key or data changed; nothing is hidden. Display only, unmeasured.

"Show me only EMBC" was **not built** — its meaning is not established (HIS CALL 2 below).

## Where his 🚫 names sit on the 🧠 page (one owner GET, 2026-11-25 ~10:35 ET, the 10:31 pass)

| surface on the 🧠 page | 🚫 mentions | position today | this build |
|---|---|---|---|
| cards | 1 (MRM) | already last (`broker_bottom`, 11-09) | header added above it |
| 🧠 from every tab | 1 of 5 rows (PLAG) | already last in its group | untouched |
| 📈 Track today | 6 of 31 rows (MRM, RMSG, PLAG ×2, BDMD, OMH) | rows 10, 16, 18, 19, 23, 25 — interleaved, newest first | untouched |
| 📈 Track last session | 13 of 80 rows | rows 9, 11, 17, 22, 37, 39, 48, 49, 56, 62, 67, 71, 80 — interleaved | untouched |
| 👀 watch line | 1 of 22 (OMH) | 4th | untouched |

22 mentions: 2 already last, 20 interleaved. This build labels 1 of the 22 and moves none. (A snapshot — stale by the
next pass.)

## The served block

`backend/chart_maps/gajjala/tab.py`, owner only, nested INSIDE the owner's `broker_flags` block (so the nothing-hidden
invariant's strip list needs no edit):

```json
"broker_flags": { …unchanged…,
  "section": {"key": "broker", "title": "🚫 not eligible at Fidelity", "text": "🚫 not eligible at Fidelity · 1",
              "hint": null, "n": 1, "symbols": ["MRM"]} }
```

- Shape = the 👀 Watch section block (`gajjala_watch.sections.sections_block`): `BROKER_SECTION_KEYS =
  ("key", "title", "text", "hint", "n", "symbols")`; `text` = `BROKER_SECTION_TEXT` (`"{title} · {n}"`, pinned equal to
  `gajjala_watch.constants.SECTION_TEXT`) over `BROKER_FLAG_TEXT` — the ONE served word. No new phrase.
- `symbols` = each tile's own spelling, in the board's own order (`potential.order_key`, then `broker_bottom`).
- Built by `broker_section(tiles, flags)` (membership through `broker_text_for`, "." / "-" folded) and set in place by
  `_broker_section_tag(out, flags, sub_k)`, ONE `_soft("broker section", …)` line in `build` right after
  `_broker_tag(out, flags)`, outside every 1-minute / 🧪 guard.
- `broker_block`, `broker_bottom`, every `broker_bottom(` call, `POT_ORDER_TEXT`, `BROKER_BOTTOM_TEXT`, `focus_block`,
  `_potential_strip`, `_track_block` are byte-identical. No `rules_info.py` line (no rule added).

## The rules

- **Owner-only.** It lives inside `broker_flags`; a non-owner is served `broker_flags: null` as before — same tile order,
  no section.
- **Absent at 0.** No card on his list (or an empty list, or a listed name not on today's board) → the key is NOT set; the
  payload is byte-identical to before 2026-11-25.
- **Tail guard.** The listed cards must be exactly the tail of `tiles`; otherwise no key (never label an unlisted card).
- **ONE sub gate + kill switch.** `BROKER_SECTION_SUBS = (GC.POTENTIAL_SUB,)` — the FE holds no sub list. `()` turns it
  off everywhere with no FE change. Served on the 🧠 sub of 🚩 5-min, the 1-minute variant and 🧪 Audited (one shared
  branch); never on any other sub. 🥇 Luk is a separate package — out of scope.
- **A raising helper** logs and serves no key; the board, its tiles and their tags build as before.
- **A list read fault** fails open to the seed (AMENDMENTS12 F5) — the section then names the seed's cards and
  `fault_text` is served beside it, as before.

## The fold constant

`BROKER_SECTION_FOLDED_DEFAULT = False` (MINE — HIS CALL). `True` serves `folded_default: true` → the PHONE shows the
section folded until he opens it (the FE package reads it; desktop never folds). Shipped open: a default that hides a
card is his call.

## Tests

`backend/tests/test_gajjala_broker_section_2026_11_25.py` — the words and the Watch shape; the exact owner block naming
the tail; two flagged keep the board order; NEGATIVE nothing moved or dropped (vs the kill switch); NEGATIVE empty list /
a name off the board → no key; NEGATIVE byte identity at 0 + the kill switch (`BROKER_SECTION_SUBS = ()`) — the ONLY
difference is the key; NEGATIVE non-owner (`False, None, 1, "yes", object()`); NEGATIVE every other sub serves no key
(and widening the gate serves it — the gate is what blocks); limit 1; the unit (None / empty / not the tail / junk rows /
"." "-" fold); folded_default; the seed on a read fault; NEGATIVE a raising helper; NEGATIVE counts, 📈 track, 👀 watch,
🧠-from-every-tab and the setup sub's strip rows equal with the section on and off, and the pass modules never name it;
a `?focus=` into the section; the 1-minute and 🧪 variants; the call's place in `build`.

## HIS CALL

**Blocking — ask first, with the table above.** What is built is safe to ship or switch off either way.

1. **What should move?** On the 🧠 page his 🚫 cards were ALREADY last, so the cards are probably not what he means.
   Built = reading A only. A. the cards: name the bottom group (BUILT — a header, nothing moves). B. 📈 Track rows to a
   bottom group (changes that list's order). C. the 👀 watch line (OMH 4th of 22). D. seat 🚫 names in a bottom section of
   the 👀 Watch tab (a seat-rule change). E. demote the 🚫 card into the "🧠 from every tab" list (removes a card — a hide;
   not done). Which, one or several?
2. **"Show me only EMBC"** — not built. When he wrote (the 10:21 pass) EMBC was a 🧠 card beside ALGS, BENF, XXII, WHLR
   and MRM 🚫 (reconstructed from the Track timelines); at 10:26 it flipped to "partial — a rule failed" and left the 🧠
   cards. Readings, none chosen: a. a one-name view (hides every other card); b. the result he expects from line 1 — which
   would mean ALGS, BENF, XXII, WHLR are not tradeable at his broker, yet none is on his 25-name list (his list is the
   only eligibility source); c. a one-off look — the Track row's own link
   `/chart-maps?tab=gajjala&sub=horizontal_fade&focus=EMBC`. What should show only EMBC?

Not blocking (shipped defaults, each one constant or one line):

3. The header is a new always-visible served line between cards (the 11-24 landing rule sends explanation text into the
   ⓘ fold). Keep the label, or a wordless line with the words in the fold?
4. The desktop in-grid header is new — the 👀 Watch draws none on desktop. Keep it?
5. Phone default open (`BROKER_SECTION_FOLDED_DEFAULT = False`); fold by default like ✅ / ⛔🩳🔒 on 👀 Watch?
6. Header words: the one served word + count. A shorter second phrase would be a second served wording.
7. Scope: 🧠 only. Every card board? One constant (`BROKER_SECTION_SUBS`).
8. The 🔝 Focus divider and this header sit back to back on today's board — keep both?
9. Desktop has no fold. Want one?
10. Open defect, not touched: `test_gajjala_verified_rules.py::test_used_by_and_constants_pin_both_ways` is red on
    2268c461 (K11_MIN_SESSION_VOLUME has no Playbook item naming it). Fix separately?
