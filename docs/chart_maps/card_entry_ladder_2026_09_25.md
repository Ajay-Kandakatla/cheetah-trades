# 📋 Chart Maps card = entry ladder (2026-09-25)

**Display only.** No gate, sort, alert, threshold or served number changed. Frontend only; the payload and every
backend pin are untouched.

## The ask, verbatim

Ajay 2026-09-24:

> "Can you organize the chips on the cards they very over whelming we have touch a similar feature in the past see if
> you can reuse some of that work. I want them to categorized in a good way so I have enough info for entry of a stock."

His answers 2026-09-25: "Yes, build the ladder"; buy price shown as **Zone + entry**; the page-level **⊞ Expand all**
"Yes, off by default".

## What the card is now

One labelled rung per entry question, read top to bottom. A rung with nothing in it draws nothing.

| Rung | Holds |
|---|---|
| head | symbol, name, then what the company IS: theme, 🚀 growth, 🎪 promo, served company facts (Sales, 💎, cap, Recent IPO). `+ Signals` and `TV ↗` sit top-right |
| **ENTRY** | 🎯 READY / WATCH / ⛔ (served), extra served reasons as `· room < 5%`, tier and 0DTE verdicts, vetoes (🔪 falling knife, Reports …, S4/S3 stage, recycled ticker, `-x% vs your cost` first), and the zone pill **only when it disagrees with the board** — e.g. `At Supply · caution`, amber |
| **PRICE** | position pills, the approach sentence as a coloured line (green reversal / amber falling / grey settling), the ⚡ momentum burst (only while its box is ticked), ⚡ tape pills, 💰 / 🔻 money flow |
| chart | unchanged |
| **SETUP** | pattern tabs only: the why line when it is not a copy of PRICE, unclaimed stats, and every served badge the classifier does not know (the safety net — a new chip lands on the face, never in the fold) |
| **PLAN** | `Buy zone 94.86–97.08 · entry 96.09` (served `enterable.band` + the BUY line; no band → `Entry 96.09`), Stop, Target (his Cost / Your stop on Holdings), R:R, room and the other served room stats, `Last` when it differs from every plan price, room pills, the 🪜 line |
| **TIMING** | 📌 board days / 🆕, Back in, Since …, then the study run: KC, then the AMD verdict, then the 🌀 raids chip, then `▸ more · N` |
| **▸ more** | RISK (Break-even, Liquidity, Knife, Last when it equals a plan price), TAPE (🐆/🐘, Float/day, Dark, 🧲, 🛡️ put wall, Flow …), FLOOR (🎯 swept, 🔪 band broken, Liquidity swept, Band), SECTOR (heat pill or Sector flow), READS (🧨, the agreeing zone pill `At Demand · favorable`, 🎯 n/a, SMC · uncited, trend-gate premise, calendar: no record) |

- **Plan prices print with the "Trade lines" box unticked.** `filterTile` copies the plan's own lines (the Trade-lines
  and Your-position families, by the same `lineGroup` the checkboxes use) into `plan_lines` before it strips them.
- **Prices** go through `pxText` in `lib/chartMaps.ts` (3 dp under $1, else 2; the now-line uses the same function). A
  non-finite price drops its row, so "NaN" never prints.
- **Printed once** (render-time, strict string equality only; if two strings differ, both print): the why-line tail
  (== the approach line; its head word moves onto the zone pill), `Bands` (== the 🪜 sentence), `On board` (== the 📌
  pill's N), `Sector flow (5d)` (a substring of the heat pill), `Float/day` (only when the 🐆/🐘 pill carries the same
  string — today 2.7 vs 2.66 differ, so both stay in TAPE).
- **Folded ≠ removed.** The fold is `hidden`, never unmounted; every read stays in the DOM and on the ticker page. The
  button turns amber with `⚠n` when a warn-toned served chip is folded, and its title names them. Vetoes never fold.
- **⊞ Expand all / ⊟ Collapse all** beside the ⚡ box on every board tab: opens every card's fold at once. Off by
  default, remembered per browser under `cm.expandMore` (`'open'` / `'closed'`, the 🔥 Hottest `hs.expandAll`
  convention). A card opened or closed by hand keeps that until ⊞ is pressed again.
- **Wrappers** that print chips beside the tile pass `outerChips` so each chip prints once: Support
  (`SUPPORT_OUTER_CHIPS`: growth, promo, explosive, enterable), POTUS (+ watch), 9 EMA (growth, explosive, enterable).

## Repair round (2026-09-25)

- **PLAN names a line by what it is.** The fixed words Stop / Target / Cost / Your stop print only when the served
  label is the canonical one (`STOP`, `TARGET`, `your cost …`, `your stop …`; `planLineKey` in `lib/cardLadder.ts`).
  Any other label prints verbatim as the key: Breaking's lid reads `BREAK 52.00`, never `Target 52.00` under a
  stock at 54; a `200d` MA line served with the stop tone reads `200d`.
- **🎯 / 🧨 beside a wrapper skip only on equal text.** The Support / POTUS / 9 EMA heads read 🎯 and 🧨 from the
  room endpoint; the tile reads its own served copy. `outerChipsFor` (`lib/outerChips.ts`) drops the tile's copy only
  when both chip strings are identical; while the room read is loading, failed, or says something else, the tile keeps
  its own. 🚀 / 🎪 / + Signals are the same component on the same symbol and stay skipped.
- **🎯 in PRICE** is only the Gabbar position shape (`🎯 In Gabbar band (…)`, `🎯 x% above|below …`); any other 🎯
  badge falls to SETUP, the unknown-badge safety net.
- **Live check** `pages/ChartMapsLadder.live.test.tsx` renders every tile of the served zones / supply / amd boards
  (fixture `components/__fixtures__/card_ladder_live_2026_09_25.json`, read-only GETs) plus the spec tiles: rung
  order, no empty rung, buy zone = `enterable.band`, fold count = folded DOM items, amber on a folded warn, nothing
  junk, every served badge and stat printed (bar the named dedupes), ⚡ in PRICE only while ticked.
- **Mobile:** chips in the rungs wrap at spaces (`white-space: normal`); nothing is cut mid-word; the only ellipsis
  on the card is the company name.

## Where it lives

- `frontend/src/lib/cardLadder.ts` — the classifier (strings only, no number parsed), `orderChips`, the ⊞ preference.
- `frontend/src/components/PatternChart.tsx` — the rungs, the plan grid, the fold, `outerChips`, `expandAll`.
- `frontend/src/lib/chartOverlays.ts` — `isPlanLine`, `plan_lines`. `frontend/src/lib/chartMaps.ts` — `pxText`.
- `frontend/src/pages/ChartMaps.tsx` — the ⊞ button. `frontend/src/styles.css` — the ladder block at the end.
- Contract `📋 the Chart Maps card reads as an entry ladder …` in `frontend/scripts/contracts.mjs`; ✨
  `card-entry-ladder-2026-09-25`.
- Tests: `lib/cardLadder.test.ts` (live VOYA / CBL / HCSG + an ORKA-shaped worst case, every served literal, 15
  negatives + the repair cases), `components/PatternChart.ladder.test.tsx`, `components/PatternChart.outerChips.test.tsx`,
  `pages/ChartMapsExpandAll.test.tsx`, `pages/ChartMapsLadder.live.test.tsx`, `lib/chartOverlays.test.ts` (plan_lines).

## Open (his call)

- The ⚡ burst badge (45 chars) wraps; a short served form is wt-burst's call.
- The Signal Lab tab passes no `outerChips`: its tile rows print no chip strip beside the tile (the strip is only on
  no-data rows), so skipping chips there would remove them.
- 0DTE prints the first call wall only.
- Every on-face zone pill is amber (`warn`), including `Clear Runway` / `Mid Range`; his call #4 named only
  `At Supply · caution`. Live data on 2026-09-25 carried only At_Supply and At_Demand. On Breaking, "Buy zone" is
  the broken lid (the served enterable band for supply_break) — a `Lid` label is his call.
- The backend `short` / `rung` fields and `At_Demand` → `At demand` at the source are a later api branch.
