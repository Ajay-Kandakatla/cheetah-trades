# ⛔ SSR "new today" list on the 🩳 High SI sub — the served block (2026-11-24)

Spec: `ssrlist` revision 2, WP `be-block` (§3.3). DISPLAY on the GET. **UNMEASURED. Not advice.**
The engine (`short_interest/ssr.py` `new_triggers`) is WP `be-engine` (`docs/gajjala/ssr_new_triggers_engine_2026_11_24.md`);
the panel is WP `fe` (`docs/gajjala/high_si_ssr_new_frontend_2026_11_24.md`).

## His words

Ajay 2026-11-24, verbatim and in order:

> "What are the SSR stocks today"
> "Can you add it to short interest tab"
> "The new ones"

"The new ones" = the names whose short-sale restriction STARTED in the session shown (not the ~447 carried from the
day before).

## What shipped (this package)

| Piece | Where |
|---|---|
| `ssr_new_block(listed, *, session, now, tf, v, ssr_read, si_read)` — copies the engine's texts, splits its rows into four folds, orders each; never raises (→ `ssr_new_fault()`) | `backend/chart_maps/gajjala/high_si.py` |
| `_ssr_read(session, now)` — the module's ONE (lazy) import of the ⛔ engine: `SSR.new_triggers(session, now=now)` | same |
| `ssr_si_text` (the house 🩳 chip as is, any basis), `ssr_tiered`, `ssr_new_rank`, `ssr_new_fault`, `ssr_new_rules_line` (the ℹ️ sentence) | same |
| `block()` gains `ssr_read=None, ssr_si_read=None` and serves `high_si.ssr_new` after `faults_text`, in its own try. The 🩳 cards, their order and every existing key are unchanged; `tab.py` is not edited | same |
| 42 tests (negatives named `test_NEGATIVE_*`) | `backend/tests/test_gajjala_high_si_ssr_new_2026_11_24.py` |

## The default cut (HIS CALL 1)

Four folds, by the tab's own two facts, in this order — an empty fold is omitted:

| Key | Fold | 12:04 ET 11-24 read (spec §1.5) |
|---|---|---|
| `list_high` | on GG's 🚩 list AND High / EXTREME house tier — its line names its tickers | 20 |
| `list_other` | on his list, lower tier or not tiered | 30 (11 not tiered) |
| `high` | High / EXTREME, not on his list | 93 |
| `rest` | every other name | 608 (485 not tiered) |

Unknown is never a yes: short interest unread → no `list_high` / `high` fold (`si_note` says so); his list empty or
unread → no `list_*` fold (`list_note`). The tier is the ONLY cut — a name with no tier is never High / EXTREME,
whatever its chip prints. Inside each fold: EXTREME, High, Moderate, Low, then the names not tiered; inside each the
highest % of float; a name with no finite % last; A→Z. Every fold is closed (`SSR_NEW_OPEN = ()`, HIS CALL 2).

## Tiered / not tiered [C2]

A house tier needs `headline_basis == "float"` AND an ok read (`SR.si_tier`). At 12:04 ET: **255 tiered / 496 not
tiered** of 751 — not tiered = 453 with a record but no float on file, 23 with no record doc, 17 on a shares-outstanding
basis, 2 stale, 1 `no_record`. So the High / EXTREME counts are a floor: `tier_note` says it in the head, `n_untiered`
carries the total, and " (N not tiered)" rides `list_other` and `rest` only (never "(0 not tiered)").
The 🩳 text on a row is the house chip for EVERY name that has one (727 of 751 at 12:04), tiered or not.

## Payload cost (measured, spec §1.5)

Added to the `?sub=high_si` GET: **160,307 B raw (+89%) · 12,542 B gzip (+30%)** for 751 rows; the `rest` fold alone
128,497 B raw · 9,941 B gzip. Engine 30 ms + SI read 28 ms on a 0.88 s GET. Not capped (no invented number).

## Accuracy — never one figure alone

Nearly every row is `computed` (this app's own 10% read). On file: 27 of 28 on ONE NYSE-side day (a selected
subsample) AND, whole market the same day, precision **at most 447 / 493 = 90.7% (Wilson 95% 87.8–93.0%)** — an upper
bound, not a measurement. Owed: the first both-side precision and recall, `scripts/ssr_agreement.py 2026-11-24` at/after
04:20 ET 11-25. Nothing here is measured as an edge.

## HIS CALL (defaults shown, none decided for him — spec §7)

1. The cut and the order — the four folds above. Alternatives: three folds; a fifth fold for the not-tiered names;
   `rest` as a count only (80% of the added bytes); newest trigger first; biggest drop first.
2. Open or folded — every fold closed; `list_high` names its tickers in its line.
3. 👀 Watch — not merged (a standing pin bans the Watch read here; owner-only data on a shared board; 0 names gained today).
4. Triggered again — counted as new and marked "also triggered <prior day>" (101 at 12:04). Alternative: leave them out.
5. Before 09:30 — one sentence, no list (the engine's `pre_open`). Alternative: keep the last session's list until 09:30
   (needs a three-file-day read).
6. Computed names — shown "computed" until an exchange list read here carries them; never removed for being missing.
7. The 🩳 text per row = the house chip as is (727 of 751). Alternatives: only tiered names (255); a shorter text.
8. The "through" date printed once in the head.
9. Placement — inside the 🩳 panel, above the cards, before the ⓘ fold.
10. Any use beyond a list (sort the 🩳 cards by it, a push, a filter) — none built.
11. Wording — titles, "by HH:MM", "computed", "not tiered", the fold lines, the ℹ️ sentence.
12. Should this list ask for the exchange files itself? Default no: `high_si.py` is a pinned display reader; the
    cards' ⛔ tag GET asks. With no card open after 20:10 ET the NYSE rows do not arrive and rows stay "computed".

## Limits

- The section rides the 🩳 block: when the short-interest read itself faults, the block is None and no ⛔ section prints.
- `listed == {}` cannot tell empty from unread — `list_note` says both.
- A list-only name arrives in the list's spelling; the SI lookup is exact, so it may print without 🩳 — never a wrong 🩳.
- Two SI reads per build on this sub (the 🩳 cards + these rows), both through `si_blocks` (the ONE `SR.si_map` call).
- No rows → the SI reader is not called; `counts_text`, `si_note`, `list_note` and `order_note` are then None.
- Display only: no push, no gate, no 🩳 card order change, no lane. Pinned by the display-only and source-guard tests.
