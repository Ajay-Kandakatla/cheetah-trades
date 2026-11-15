# 👀 Gajjala's Watch — the dashboard (frontend, 2026-11-15)

Spec: gajjala-watch spec §3.8, work package WP-C. Backend routes and payload: `docs/gajjala/watch_dashboard_2026_11_15.md`. Minute loop and cross push: `docs/gajjala/watch_cross_alerts_2026_11_15.md`.

## His words

> "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove tickers from the dashboard.
>
> When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear distinction or may be a brighter and thicker 21 EMA and 9 EMA, from the videos I notice that when ever 9 EMA crosses over 21 EMA on uptrend is where the bullish momentum started I need alerts on these from 1 min to I can be ready... I think the cross over is slow but once it picks up its very rapid.."

> "I have a 27 inch monitor I wanna fit 3x3 tikers on watch at any given time on this tashboard"

> "Any chart I view make sure you are showing me from 4 AM for historical behaviour and also the right side with gaps to see where it might go"

## What ships

| Piece | File |
|---|---|
| Tab `gajjala_watch` ("👀 Gajjala's Watch"), right after 🚩 Gajjala's 1-min, before 🥇 Luk's; not a tile board; ⚡ exempt ("your own tickers in your order — never ranked") | `lib/chartMaps.ts`, `lib/momentumBurst.ts` |
| Routes, payload types, parser, replay palette, chart heights | `lib/gajjalaWatch.ts` |
| The board | `components/GajjalaWatchBoard.tsx`, `styles/gajjalaWatch.css` |
| Three optional chart props (`chartOnly`, `emaStyle="bold"`, `axis`) | `components/PatternChart.tsx` |
| Owner-only tab, the wide page | `pages/ChartMaps.tsx` |

Every word on the board is served by the backend (`chart_maps/gajjala_watch/payload.py`). The frontend writes one sentence of its own, "Could not load the watch.", for when the request fails and nothing was served. A served `{state: "error", reason}` (`payload.error_payload`) prints **its reason verbatim** — on the first load in place of the board, on a refresh in the head above the board that stays up (2026-11-15 fix #4). It also uses a few marks: ⚠️ on a served stale flag, ✕, ℹ️ and "·".

## Owner only

- The tab is offered to the primary owner (`/auth/me` `is_primary_admin`).
- While `/auth/me` is still loading, the tab is offered anyway, so his push deep link (`?tab=gajjala_watch&focus=SYM`) does not bounce.
- A loaded non-owner (a co-owner, or nobody signed in) does not see the tab. Their `?tab=gajjala_watch` lands on the first tab, the same way `catalysts` works.
- The server is the real gate: anyone else gets `owner_only`, and the board prints only the served reason.
- The frontend never compares emails, and no email address is in any watch source (a test checks this).

## Layout: 3×3 on his 27-inch monitor (HIS CALL #10, #18)

- **Grid.** Above 1260 px: 3 columns. 641–1260 px: 2 columns. 640 px and under: 1 column. Every column is `minmax(0, 1fr)`.
- **Wide page.** On this tab only, the page drops the 1500 px Chart Maps cap (`cm-page--wide`, `max-width: none`). Every other tab keeps the cap; a test checks the class on other tabs.
- **Tile.** The head holds:
  - SYM;
  - the served row text, with the session stamp and as-of time (⚠️ when stale);
  - 🔔 chips for alerts that rang;
  - one Yahoo ↗ link;
  - ✕ to remove the ticker (a DELETE, with no confirm).

  Below the head is the replay's dark panel: the **1-min chart full width on top**, and the **3-min and 5-min charts side by side** under it (stacked on a phone).
- **Captions.** Each chart is captioned `label · K5 ✓/✗/—`, plus the served `held` chip when there is one. The K5 rule, the push sentence and the honesty line print **once**, in the collapsed ℹ️ in the head, never under every chart.
- **Heights** (viewBox units; PatternChart `W` = 620): 1-min **120**, 3-min / 5-min **180**, phone **190** (the house default). Above the phone break these are now only the starting point and the share of the tile height each chart gets (see "3 rows on one screen" below); on a phone they are used as they are.

  **The first arithmetic was wrong (corrected 2026-11-15).** It assumed ≈ 236 px above the grid. A Playwright render of the real page (scratch Vite, every API call mocked) measured the grid's top at **357 px** and **56 px** of page below it. With fixed heights the 9th tile ended at **1459 px** on a 1440 px screen and at **1316 px** on 1080 — the 3×3 did not fit on either.

  | Screen | Above the grid | Below | Room for 3 rows + 2 × 13 gaps | Row | Fixed-height tile (before) |
  |---|---|---|---|---|---|
  | 2560×1440 | 357 | 56 | 1440 − 357 − 56 − 26 = 1001 | **333 px** | 359 px (overflowed) |
  | 1920×1080 | 357 | 56 | 1080 − 357 − 56 − 26 = 641 | **213 px** | 311 px (overflowed) |

## 3 rows on one screen (2026-11-15 fix #3)

His words: "I have a 27 inch monitor I wanna fit 3x3 tikers on watch at any given time on this tashboard".

- **Rows from the viewport.** Above 640 px the board measures the grid's top on the page and what sits below it (ancestors' bottom padding and margins plus any element laid out under the grid, never the slack of a short page). It sets `--ggw-row-h = (innerHeight − top − below − 2 gaps) / 3` and adds `.ggw-grid--fit` (`lib/gajjalaWatch` `ggwFitRowHeight`). It re-measures on a window resize and when the board head changes size.
- **Charts fill the row.** In a fitted tile the head and captions keep their size and the charts take the rest. The 1-min chart and the 3-/5-min pair split it 120 : 90, the same proportion `GGW_CHART_H` gives them at any width (`GGW_FIT_GROW`; the pair is half as wide). Each chart box is measured and its viewBox height is set to fill it exactly (`ggwFitViewBoxH`): no stretching, no overflow.
- **Floor.** A row is never shorter than **200 px** (`GGW_FIT_ROW_MIN_PX`). This number is MINE, a layout choice, and moving it is HIS CALL. A shorter window scrolls instead of shrinking the charts further.
- **Phone.** At 640 px and under nothing changes: one scrolling column at the house 190.
- **Measured** (Playwright, mocked API, 9 tickers, light and dark identical):

  | Screen | Tile | 1-min chart | 3-/5-min chart | 9 tiles on screen | Page scroll |
  |---|---|---|---|---|---|
  | 2560×1440 | 333 px | 794 × 143 px | 393 × 105 px | yes (9th ends 1382) | none |
  | 1920×1080 | 213 px | 581 × 74 px | 286 × 54 px | yes (9th ends 1022) | none |
  | 1280×800 | 200 px (floor) | 367 × 67 px | 180 × 48 px | no | scrolls |
  | 430×932 | 460 px | 362 × 112 px | 362 × 112 px | one column | scrolls, as before |

  At 1920×1080 the charts are small. The 357 px above the grid (nav, Chart Maps head, pinned tabs, the WHY box, Enterable only) belongs to the Chart Maps page, not to this tab. Shrinking that is HIS CALL.

## The look: the replay video

- **Palette provenance.** `eod-audits/replays/replay_gif.py:576-581` PALETTE: bg (13,17,23), grid (38,43,52), text (225,228,232), dim (135,142,152), up (38,186,104), down (235,72,72). The 9 EMA is `#FACC15` and the 21 EMA is `#BE78FF` (`replay_gif.py:579`). Both lines are 2 px, drawn over the candles (`replay_video.py:258-260`, `:339-350`).
- **`.ggw-dark`** sets `--surface`, `--bg-raised`, `--bg-sunken` and `--cm-card` to the replay background, and `--rule`, `--ink`, `--text-muted`, `--positive` and `--negative` to the replay colours. The chart-only tile therefore paints the replay panel.
- **`lib/chartMaps.ts` `EMA_BOLD`** holds the two colours and widths. It is the one source for the chart, the right-edge EMA price labels (fix #2) and the legend swatches.
- **The tile's own text palette (2026-11-15 fix #1).** The tile is always dark (`--cm-card` rgb(22, 26, 34), the colour it always painted). In the light theme it used to inherit the page `--ink` #1A1A1A, so SYM, ✕ and Yahoo ↗ were dark on dark. `.ggw-tile` now sets the replay's `--ink`, `--text-muted`, `--rule`, `--positive` and `--negative`, plus `color: var(--ink)`. Measured light and dark: SYM / ✕ / Yahoo ↗ are rgb(225, 228, 232) on rgb(22, 26, 34).

## PatternChart props: each default draws exactly as before

PatternChart draws every Chart Maps card, so all three props are optional and change nothing when they are left out. Before merging, 182 renders of every fixture tile were compared with the props absent, hover included: the HTML was byte-identical before and after.

- **`chartOnly`** — a plain `div.cm-tile.cm-tile-chart-only`, never a router link, so there is no SEPA link anywhere on the board. The head, rungs, footer and ▸ more are skipped. The svg, hover crosshair and markers stay.
- **`emaStyle="bold"`** — the `ema9` / `ema21` curves are drawn **after the candles** (21 first, then 9 on top) in `EMA_BOLD`, with `vector-effect: non-scaling-stroke` and opacity 1. The 9/21 cross diamonds are taken out of the marker pass and drawn in their own group after the bold EMAs, so a cross is never hidden under the lines. Other curves keep their look and their place under the candles.
  - Since 2026-11-15 (fix #2) the right-edge `9 EMA …` / `21 EMA …` price labels and their pointers are also drawn in `EMA_BOLD` (`boldEmaLabels`). They used to stay blue and amber beside a gold 9 line and a violet 21 line. A label is recoloured only when both its text and its colour are the EMA's own, so a served line in the same tone keeps its colour. Without the prop the label array is returned untouched. 586 renders of 293 fixture tiles at two heights, without the prop, were compared with the pre-fix PatternChart: the HTML was identical (React's generated ids aside).
- **`axis`** — the served time axis (`{slots, x, shade, ticks}`; backend `build.axis`):
  - One x mapper, `sx(i) = xFor(axis.x[i], axis.slots)`, is used at every x site. Bar width and hover use `axis.slots`, and hover snaps to the nearest printed bar (`nearestAxisBar`).
  - The served pre-market / after-hours shade replaces the extended-hours runs, and the served hourly ticks replace the date ticks.
  - Slots right of the last bar stay empty out to the close ("the right side with gaps").
  - Candle bodies are `bw × 0.64` with **no 1.4 floor**: at 720 one-minute slots that is ≈ 1.07 CSS px per minute, so the bars are thin, as in the replay.
  - An axis whose `x` does not match the bars is ignored.

## Cadence (no live poll)

- One `setTimeout` chain re-GETs the full board at the served `refresh_sec` while the page is visible. A hidden page re-arms the timer without fetching.
- `refresh_sec == 0` with a served `next_window_sec` → **one** re-GET at it, then the chain follows whatever that answer serves.
- While a row is `pending`: GET `?symbols=<pending names>` only, every `pending_poll_sec`, each name for at most `pending_wait_max_sec`. The rows are merged in place, and the board order and head never change.
- After an add or a remove: one full re-GET.
- **No `useCardLive` and no live-card poll.** The minute GET is what moves the bars (spec C4.5). A source guard and a request check pin this.
- `?focus=SYM` (the push deep link) scrolls that tile into view and outlines it once.

## Not on this tab

- The house chips (🚀 growth, 🧨 explosive, 🩳 short interest, 🎯 enterable): each tile is the chart alone ("Not the SEPA"). The frontend contracts that require these chips on every non-board tab need a written exemption for `gajjala_watch`. That belongs to the main session's `contracts.mjs` block.
- Volume columns keep the house 1.4 minimum width even under `axis`. The spec drops the floor for candle bodies only.

UNMEASURED — a 9/21 cross is information, not an entry. Not advice.
