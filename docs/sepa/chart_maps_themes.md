# Theme priority — which build-out names lead the Chart Maps board

**Code:** `backend/sepa/universe.py` (`THEME_UNIVERSE`, `THEME_PRIORITY`, `theme_rank`) ·
`backend/chart_maps/board.py` (`_sort_key`, `_spread`, `MAX_PER_THEME`) ·
**Tests:** `backend/tests/test_theme_priority.py`, `frontend/src/lib/chartMaps.test.ts`

> Ajay 2026-08-16: *"can you check if ASTS and RKLB are in the list.. I wonder
> why I don't see them"* … *"I do want us to give priority to Space technology,
> Quantum, Semis"* … *"Fiber optics, and Robotic components or any potential
> bottlenecks for AI that are going to be the next big thing.. after Semis and
> HBM."*

## The answer to the ASTS/RKLB question

**They were never missing from the universe.** Both are in the curated list in
`universe.py`, and the board scans `sp1500_plus`, which unions it.

They are absent from the board because **they have no VCP setup**. Measured
against the 2026-08-14 scan:

| | ASTS | RKLB |
|---|---|---|
| `entry_setup.type` | none | none |
| `vcp.tightness` | 34 | 8 |
| `rs_rank` | 32 | 59 |
| `stage` | 1 | 3 |

`strong_vcp_reject()` returns `"no VCP setup"` for both — the very first gate.
Ranking never enters into it. Neither name is in a base.

## The measurement that matters more

Running `strong_vcp_reject` over all 82 theme names in the same scan:

| Reason | Count |
|---|---|
| no VCP setup | 69 |
| not in scan output | 8 |
| base not tight enough | 4 |
| fails the trend template | 1 |
| **passes** | **0** |

And the setup rate, theme names vs the whole scan:

| | VCP setups | Rate |
|---|---|---|
| Theme names (in scan) | 5 / 74 | **6.8%** |
| Whole scan | 618 / 2,974 | **20.8%** |

Stage distribution across the theme names: **Stage 3 = 31 (42%)**, Stage 1 = 18,
Stage 2 = 17 (23%), Stage 4 = 8.

So the AI / space / quantum complex is currently **three times less likely to be
in a VCP base than the market**, and the largest single bucket is Stage 3 —
topping. That is a market condition, not a scanner defect, and no amount of
priority ordering changes it. **Priority decides the order of names that pass;
it cannot promote a name that fails.**

## Priority

`THEME_PRIORITY`, most-wanted first — Ajay's stated order, then the bottlenecks:

| Rank | Theme | What it covers |
|---|---|---|
| 0 | `space` | launch, satellites, imagery, satcom |
| 1 | `quantum` | quantum computing |
| 2 | `ai_semis` | compute, HBM/storage, metrology |
| 3 | `optical` | transceivers, lasers, fibre, connectors |
| 4 | `robotics` | robotic components, physical AI |
| 5 | `ai_infra` | power, cooling, racks |
| 6 | `nuclear` | generation |

Before this, `_sort_key` was binary — theme or not. It could answer *"is this a
theme name?"* but never *"which theme leads?"*.

A theme with no priority entry sorts at `UNKNOWN_THEME_RANK` (50) — behind every
ranked theme, still ahead of every untagged name. Adding a roster and forgetting
the priority entry degrades; it does not hide the names.

## Roster construction

Every ticker was probed against our own price feed (260 daily bars + 50-day
dollar volume) before being added. Nothing came from memory or an internet list.
All 82 resolve.

Deliberate exclusions, with the reason:

- **Defence primes** (LMT, NOC, RTX, BA) — conglomerates where space is a
  segment. Tagging them `space` puts a defence-budget story at the top of the
  board.
- **Broken businesses** — SPCE ($3.32), MNTS ($4.84).
- **Too thin to chart honestly** — SPIR $17M/day, LAZR $18M, ATS $5M, KRNT $4M,
  INVZ $2M (a $0.37 share).
- **Not the theme** — ATRO/TDG/HEI are aerostructures and aftermarket parts;
  JNPR/EXTR/NTAP are networking and storage, not optics; CLS/FLEX assemble
  racks, so they went to `ai_infra` rather than `optical`.

**A ticker belongs to exactly one roster.** `THEME_BY_TICKER` is last-wins, so a
duplicate silently retags a name and changes its priority. NVDA is the standing
temptation — physical-AI platform and semi both — and it stays in `ai_semis`.
`_assert_themes_disjoint()` raises at import rather than failing quietly at sort
time.

## The per-theme cap

`MAX_PER_THEME = 6`.

Ordering alone is not enough once the rosters are this big — space + quantum +
ai_semis is 33 names, so on a strong day for one theme the top roster could take
all 24 slots and the optical and robotics setups would never appear.

**Its honest limit, pinned in a test:** when nothing else is setting up, the
capped theme's overflow fills the remaining slots rather than shipping a
half-empty board. On a narrow day the board shows what is actually working. The
cap reserves slots for competition; it does not manufacture it.

The cap applies only when `themes_first=True`. The winners tab passes `False` —
a historical win is a historical win regardless of sector.

## Not advice

Themes decide who gets **looked at** and in what order. Nothing here bypasses a
gate: theme names enter the same trend, knife and liquidity filters as every
other name, and `is_buyable` remains the strict entry gate. A theme tag is not a
reason to own something.
