# 🚀 Explosive Growth — sorting by demand — 2026-09-12

> Ajay: *"sort this by demand intact"*

## Why it was needed

The board ranked by sales growth and nothing else. On the 2026-09-12 build that
put the four names actually standing at an **intact demand floor** at ranks
5, 11, 14 and 20 — under fifteen names not at a band at all:

| Before (sales YoY desc) | After (demand desc) |
|---|---|
| DBRG · out · +15,961.5% | **HHH · 🧲 intact · +330.2%** |
| PTGX · out · +3,749.2% | **HNI · 🧲 intact · +145.5%** |
| LQDA · out · +1,842.7% | **ARR · 🧲 intact · +132.0%** |
| PROP · no bands · +627.4% | **RKT · 🧲 intact · +104.7%** |
| SNDK · out · +428.9% | MU · in band, pierced · +345.7% |

The one column carrying a **measured** gate was the one column you could not
order by.

## The ladder

Ordered by **distance from the one gate that measured** — `intact`, +8.6pp over
31,861 events (2026-09-09 bounce-gate study). Not by how good the name is.

| Rank | Cell | Meaning |
|---|---|---|
| 3 | `🧲 intact` | in a demand band, floor never pierced |
| 2 | `in band, pierced` | in the band, floor went — **the intact edge does not apply** |
| 1 | `out` | scanned, has bands, standing in none |
| — | `no bands` | outside the scan universe — no zone read exists |
| — | `in band, floor ?` | band is real, the floor gate never answered |

The last two are **UNKNOWN, not bad**, and sort **last in both directions** —
the same rule the 🔥 Hottest columns follow. Ranking an unknown as a zero is how
a name nobody measured floats to rank 1 of an ascending sort and reads as the
worst on the board. Verified on the live 29: ascending puts DBRG/PTGX/LQDA
(`out`, the worst *known* state) on top and leaves PROP/IPI/FF pinned at the
bottom.

## A bug this surfaced

`demandCell` tested `if (z.intact)`. A row **in a band whose floor gate threw**
(`intact: null`) fell through to `in band, pierced` — stating a fact nobody
checked. It now renders `in band, floor ?` and sorts with the unknowns. Zero
rows are in that state on today's build, but the path is reachable:
`growth/tracker._zone_read` leaves `intact` as `None` when
`alert_gates.floor_held_gate` raises, and logs at debug only.

## Why the sort runs in the browser

The opposite of the 🔥 Hottest board, deliberately. Hottest keeps only
`names_per_group` rows per sector, so a client sort there would reorder the
visible 25 and never reach the 46th name — it **must** round-trip. This payload
carries **every row the screen returned** (29 against a `MAX_ROWS = 300` cap),
so a local sort is complete. Do not "fix" this into a server sort for
consistency: it would add a round-trip that buys nothing.

## Behaviour

- Click any of the **9** headers to rank on it; click again to flip.
- A new column opens at its interesting end — descending everywhere except
  `Symbol`, which reads A→Z.
- Ties break on **sales growth desc, then symbol** — the board's own original
  order — so equal-demand rows never shuffle between renders. The tiebreak does
  **not** reverse with the direction; it is not part of the comparison.
- `sortRows` returns a **copy**. Sorting the fetched payload in place would make
  the filter memo above it depend on click order.
- **The board now opens on demand, intact first.** Click *Sales YoY* for the old
  order. The caption states the live order in words, derived from the state
  rather than retyped.

## Tests

- `frontend/src/lib/growthSort.test.ts` — 15 tests. All **8 mutations caught**:
  unknown scored as 0 · `intact: null` ranked as pierced · ladder inverted ·
  tiebreak flipping with direction · in-place sort · default reverted to sales ·
  NaN as a real number · symbol opening Z→A.
- `frontend/src/components/ExplosiveGrowth.test.tsx` — 7 added, end-to-end
  through the real component.
- Contracts: *"the growth board sorts by demand, unknown pinned last"* and
  *"the growth demand cell never calls an unknown floor pierced"*.

## What this does NOT claim

**Ordering changes what you look at first, not whether any of it works.** The
board is a discovery list with no market-cap floor (his explicit call) while the
trading engine keeps its $700M and $2 floors — a `⛔` row is real here and
refused at the broker. `intact` is the only gate on it that has ever measured.
