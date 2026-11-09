# 🌐 Yahoo ↗ — the external link-out on every chart tile (2026-11-09)

Ajay 2026-11-09, with a 🚩 Gajjala card screenshot of the `TV ↗` button: *"Instead of traderview I need yahoo finance
link here"* / *"To external ones please"*.

## What changed

| Surface | Before | Since 2026-11-09 |
|---|---|---|
| every chart tile top-right (`PatternChart`, every Chart Maps board incl. 🚩 / 🧪 / 🥇 / 1-minute) | `TV ↗` → `tradingview.com/chart/?symbol=SYM&interval=…` | `Yahoo ↗` → `https://finance.yahoo.com/quote/SYM/` |
| Support tab head (`SupportLevels`) | `TV ↗` with the current frame's interval | `Yahoo ↗`, same quote page |
| Stock detail modal (`StockDetailModal`) | TradingView embed + links | **unchanged** — a different surface, not a card link-out |

- Helper `frontend/src/lib/yahooLink.ts`: `yahooQuoteUrl(symbol)` (trim, upper-case, dot share class → Yahoo's dash,
  `encodeURIComponent`), `yahooTitle`, `YAHOO_LABEL = 'Yahoo ↗'`, `openYahoo(e, symbol)` (cancels the tile `<Link>`
  navigation, stops the bubble, `window.open(…, '_blank', 'noopener')`).
- `frontend/src/lib/tvChart.ts` (Ajay 2026-08-31 "also give me a trading view pre configured chart please") and its test
  are deleted; `PatternChart`'s `tvTf` prop and its two callers (`SessionBoard`, `SignalLabBoard`) with it. Yahoo has no
  interval parameter, so the frame is not carried.
- No data path, gate, rule or push changes. ✨ `chart-maps-yahoo-link-2026-11-09` FIRST (his two sentences verbatim).

## Tests

- `frontend/src/lib/yahooLink.test.ts` — URL shape, trim/upper-case, dash kept, dot → dash, NEGATIVE never a dot / `%2E` /
  tradingview / interval, encoding, the double-cancel click handler.
- `PatternChart.test.tsx` — the button opens the quote page without following the tile link; NEGATIVE no TradingView button,
  no `TV ↗`, no tradingview / interval in the opened URL. `PatternChart.outerChips.test.tsx`, `PatternChart.ladder.test.tsx`
  keep the button by its new name.
- `SupportLevels.test.tsx` — the head anchor's href, target, title; NEGATIVE no `TV ↗`.
- `scripts/contracts.mjs` "🌐 Yahoo link-out (2026-11-09)" — the helper's base URL, label, dash rule, open call, the two
  call sites, `tvChart.ts` absent, no `tvTf=` caller, the ✨ FIRST with both sentences.
