# Catalysts → ticker Supply & Demand (2026-09-25)

**Ask (Ajay, 2026-09-25):** "Can you help make all the catalyst pages to be going to Ticker supply and demand please?"

## What changed

Every ticker on the Chart Maps ▸ Catalysts tab (and the standalone `/catalysts` board for users without Chart Maps) opens
`/sepa/SYM?tab=supply&from=chart-maps&from_q=tab=catalysts&sub=<sub-tab>` — the ticker page's Supply & Demand tab, with the
source sub-tab carried so ← Back returns to it.

| Sub-tab / surface | Before | Now |
|---|---|---|
| 🎯 Predictions, 🔥 Frenzy | ticker button → deep-dive drawer | ticker `<a>` → Supply & Demand; 🔎 in the icon row → drawer |
| Now (candidate cards), 🌅 Pre-market | card click → drawer | card click and ticker `<a>` → Supply & Demand; 🔎 → drawer |
| 📅 Calendar | ticker button → drawer | ticker `<a>` → Supply & Demand |
| 📜 Timeline (accumulator rows, event chips, stale rows) | row / chip → drawer; dropped names not clickable | row and ticker `<a>` → Supply & Demand; dropped names link too |
| 🚨 Volume-alert strip | item → drawer | item and ticker `<a>` → Supply & Demand; × still only dismisses |
| Deep-dive drawer footer | "Open full SEPA detail" (default tab) | "Open Supply & Demand" (`tab=supply` explicit) |
| 🏛️ Russell, 🎪 Promo | already Supply & Demand | unchanged |
| "deep-dive" box in the bar | drawer | unchanged — it is a drawer lookup by design |

## How

- `CATALYST_TICKER_TAB = 'supply'` in `frontend/src/pages/Catalysts.tsx` — one constant, pinned by a contract.
- `CatTicker` — the ticker as a `TickerLink` anchor (`tab`, `fromLabel="Catalysts"`, no ★), so ⌘-click, middle-click and
  right-click → "Open in new tab" keep the tab.
- Cards and rows that cannot be an `<a>` call `openSupply` → `openTickerWithModifier(…, 'supply')` (new optional `tab`
  argument; older callers unchanged). ⌘ / Ctrl / Shift / middle-click → new tab.
- `isInnerControl(e)` — a click on a link, button or field inside a card or row belongs to that control, so the chatter
  links, the 🔎 and the × never also navigate the card.
- `ChatterDeepLinks` gained an optional `lead` slot (compact mode only) where the cards put the 🔎.

## Tests

- `frontend/src/pages/Catalysts.supplyLinks.test.tsx` — every sub-tab's links carry `tab=supply` + source; card / row /
  strip clicks land on Supply & Demand; NEGATIVES: 🔎 opens the drawer and does not navigate (4 sub-tabs), × dismiss,
  ⌘-click opens a new tab and leaves the page alone, chatter links inside a card, the deep-dive box, no bare `/sepa/SYM`.
- `frontend/src/components/TickerLink.test.tsx` — `openTickerWithModifier` with and without `tab`.
- Contract `🧭 Catalysts (2026-09-25)` in `frontend/scripts/contracts.mjs`.

Links only — nothing ranked, gated, alerted or bought differently.
