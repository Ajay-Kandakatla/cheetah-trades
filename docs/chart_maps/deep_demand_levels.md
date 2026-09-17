# Deep Demand tile — drawing every crossed demand level

2026-09-16. WP-B of the deep-levels spec. Board side only; the qualifier
(`supply_demand/deep_demand.py`) is documented in
`docs/supply_demand/deep_levels.md`.

## 2026-09-16 — the tile now draws every level price has already crossed

Ajay, verbatim:

> "For the deep demand stocks I need the logic to be, the stocks that crosses
> the first level of support and lying in second or third level of support.
> Like CRDO dropped after the earning it crossed multiple support level."

and, with a screenshot of a Deep Demand tile in front of him:

> "We are trying to catch the returning bounce touching the first level
> support. What I am expecting here is there are two level of support in this
> chart and the price is at the second level of support."

So the chart itself has to show the levels, not just the sentence. Until today
`deep_demand_tiles()` (`backend/chart_maps/board.py`) drew exactly two bands —
`top_band` in red and `second_band` in green — because `deep_demand.read()`
only ever produced those two. It now produces `broken_bands` (every level
already crossed, high→low), `levels_broken` and `level`, and the tile draws all
of them:

| what | before | now |
|---|---|---|
| bands drawn | 2 (`1st demand · broken`, `2nd demand · entering`) | 1 + N: one red per crossed level, `1st`/`2nd` …, then the green arrival band labelled with ITS ordinal (`3rd demand · entering`) |
| tile key | — | `levels_broken` (flat, reaches the FE) |
| chart window | `max(second, top)` defining swings | `max` over the arrival band AND every crossed level, still clamped by `ZONE_BARS_MAX = 252` |
| why-line | `broke its 1st demand band (X% below it), …` | unchanged at one level; `crossed N demand levels (X% below the first), …` at two |
| badge | `🩹 In 2nd demand band` | `🩹 In {ordinal(level)} demand band` — identical at level 2 |
| lid dedupe | against the single broken band | against EVERY crossed band, on its pre-clamp geometry |

Every ordinal comes from `deep_demand.ordinal()` — the board never types
`"3rd"`. `test_b1_the_ordinals_come_from_the_read_never_from_a_typed_string`
pins that, so widening `deep_demand.MAX_LEVELS_BROKEN` from 2 to 3 is still the
one-line edit the spec promised.

**Level-2 output is byte-identical to yesterday's** apart from the bug fix
below. `test_chart_maps.py:1557,1583` and
`test_deep_gabbar_review_fixes_2026_09_14.py:115,150,151,235,252` were left
untouched and stay green.

### The straddle clamp, generalised

A 1-touch band is a single swing low widened ±1.75% into a box
(`price_zones._make_zone`), and on 4/100 tiles that box straddled the band
below it — red painted over the green entry band (2026-09-14, TRU/PLD/EME/KHC).
The old clamp was written for exactly one broken band. With N, each crossed
band is clamped against the band UNDER it: the arrival band for the lowest
crossed level, the next crossed level up after that. Two rules that matter:

- the walk always references the band's **original** top, never the clamped
  `lo` — otherwise a clamp cascades upward and moves a band nobody touched;
- a band the clamp fully swallows (`hi <= lo`) is **dropped**, never inverted.

### Back-compat

A row cached before this change has `top_band`/`second_band` and no
`broken_bands`. The tile falls back to `[top_band]`, reports
`levels_broken == 1` and renders exactly as it did
(`test_b6_negative_a_row_cached_before_this_change_renders_as_one_crossed_level`).

## 2026-09-16 — bug: the why-line read "now now in the 2nd band"

From his screenshot. `_dist_text` (`board.py:465`) already returns
`"now in {inside}"` when the distance reads ≤ 0, and returns
`"{dist}% above {above}"` — with no "now" — when it does not. The deep sentence
prepended its own `"now "` so that the above-branch read correctly, and the
inside-branch therefore served:

> broke its 1st demand band (7% below it), now **now** in the 2nd band — sales …

`_dist_text` is shared with the order-block and tested-band sentences
(`board.py:2587,2594`), whose served strings read
`"falling toward … — now in the block, down 4.1% in 6 sessions"` and must not
move. So the fix is local: a new `_now_dist_text(dist, above, inside)` wrapper
that guarantees the leading "now" in BOTH branches, used only by the deep tile.
Both branches are pinned, including the untouched shared helper
(`test_b7_the_served_sentence_never_says_now_now`,
`test_b7_negative_the_shared_dist_text_is_untouched_for_every_other_board`).

## What the board does NOT claim

Depth is **not** a measured edge. The adjacent claim — that a second band under
the print catches the name — measured `no_signal` over 24,994 episodes
(`docs/supply_demand/band_structure.md`, 2026-09-16), and a bigger first support
band measured HARMFUL. So:

- **Ordering is untouched.** Still `rerank_live(rows, _order.deep_key, live)`:
  inside the arrival band first, then nearest. A 3rd-level name never jumps a
  closer 2nd-level one (`test_b8_negative_…`).
- **No new stats row.** The board is dense (Rule #5); the badge already says
  which level price is standing in.
- **The note ends with** "Depth is NOT measured yet — levels order nothing and
  gate nothing." When WP-D lands `supply_demand/deep_levels_measured.py` the
  note quotes `MEASURED["status"]` verbatim and nothing else. The note is
  scanned for "edge", "outperform", "beats" and "bounce" by
  `test_b9_negative_the_note_never_claims_an_edge`.

## The trap worth repeating

`rec["demand_zones"]` is the FOUR demand bands **nearest the print**
(`price_zones.nearest_first(...)[:MAX_ZONES_PER_SIDE]`), sorted high→low — a
sliding window, not the top of the stack. `levels_broken` therefore counts the
levels crossed **among the surfaced bands**. CRDO on 2026-09-16 truly has more
demand bands above 150.39 than the window shows. Do not read a tile's
`levels_broken` as "this is how many supports exist above it".

CRDO is also still hidden, and that is intended: its geometry already qualified
before this change. It is refused by the arrival band's quality, not by its
depth — `touches 1 < MIN_TOUCHES 2`, `strength 31 < MIN_ZONE_STRENGTH 40`.
Those two constants were not touched here; whether they earn their keep is
WP-D's Q2 and Ajay's call.

---

## 2026-09-16 (later the same day) — level 4, and a per-level filter

> "can you do level 4 and give me filters for that"
> — Ajay, 2026-09-16

Two changes, both on the board side of the deep tab.

### The cap moved 2 → 3

`deep_demand.MAX_LEVELS_BROKEN = 3` — the screen now takes an arrival at the
**2nd, 3rd or 4th** level. The one-line edit the previous entry promised; every
ordinal on the board, the note and the ℹ️ Rules panel still come from that one
constant, so nothing else was retyped.

**Four is the ceiling the served window can express**, and the module now says
so in code: `rec["demand_zones"]` is
`price_zones.nearest_first(...)[:MAX_ZONES_PER_SIDE]` with
`MAX_ZONES_PER_SIDE = 4`, so at most three bands can ever sit above the arrival
band. A module-level `assert 1 <= MAX_LEVELS_BROKEN <= MAX_ZONES_PER_SIDE - 1`
catches a later window change that would leave the cap unreachable. The cap is
**not derived** from the window — widening the window must never silently
deepen the screen — it is just bounded by it.

`MIN_TOUCHES` and `MIN_ZONE_STRENGTH` did not move. CRDO is still hidden for
the same reason as before, on quality.

### The filter — `levels`, multi-select

| key | shape |
|---|---|
| query / board param | `levels` (**string**) — `"all"` (default) or a comma list of ARRIVAL levels, `"3,4"`, `"4"` |
| parser | `deep_demand.parse_levels(spec) -> Optional[frozenset[int]]`, `None` = all |
| payload `levels` | the normalised echo — `"all"` or `"3,4"` |
| payload `level_counts` | `{"2": n, "3": n, "4": n}` — what each chip shows, computed with the filter **OFF** |
| payload `hidden_by_level` | how many tiles the filter removed this call |

Four things this contract exists to hold:

1. **It is `levels`, not `level`.** `/chart-maps?level=` already belongs to the
   **gabbar** tab (band type: aggressive / conservative 1 / conservative 2) and
   was not renamed, reused or touched.
2. **Parsing fails open.** Unknown, empty, out-of-range or non-string specs all
   parse to `None` and serve the **full** board. An empty Deep Demand tab would
   read as "nothing qualifies today", which is a lie about the market. Junk
   parts inside a list are dropped (`"2,junk,4"` → `{2, 4}`); duplicates
   collapse; the parser never returns an empty set.
3. **`level_counts` is counted with the filter off**, inside the tile loop —
   after the Bonde sales gate, the already-reversed drop and the room floor. So
   a chip counts the names at that level on this board — the same phase / room /
   sales settings, and ticking "4" does not zero the "2" and "3" chips that are
   the only way back.
4. **The filter does not reorder.** It is a `continue` inside the loop that
   already ran `rerank_live(rows, _order.deep_key, live)`: proximity first. A
   4th-level name does not outrank a closer 2nd-level one, with the filter on
   or off. Depth is still unmeasured.

The note gains **one** clause, and only when the selection is not "all":
"Showing 3rd / 4th level arrivals only — N hidden by the level filter." The
depth disclaimer stays the last sentence on the board either way.

### Population, measured over the 2,229 `zone_store` docs (2026-09-16)

| arrival level | after the band-quality gate | before it |
|---|---|---|
| 2 | 280 | 490 |
| 3 | 232 | 395 |
| 4 | **56** | 97 |

### Tests

`backend/tests/test_deep_levels_board_2026_09_16.py` — `L1`–`L8`: a 4th-level
tile draws three crossed levels; the filter keeps only what it should; the
counts are computed filter-off and survive the filter on; `hidden_by_level`
matches; an unknown spec serves the full board; a non-string `levels` (the
FastAPI `Query` object trap) is treated as "all"; the filter does not reorder;
the note names the selection only when it is not "all"; the gabbar `level`
param still works and the new keys do not leak onto its payload.
