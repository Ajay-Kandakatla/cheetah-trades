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

Every word on the board is served by the backend (`chart_maps/gajjala_watch/payload.py`). The frontend writes one sentence of its own, "Could not load the watch.", for when the request fails and nothing was served. It also uses a few marks: ⚠️ on a served stale flag, ✕, ℹ️ and "·".

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
- **Heights** (viewBox units; PatternChart `W` = 620): 1-min **120**, 3-min / 5-min **180**, phone **190** (the house default).

  Arithmetic at 2560×1440 (≈ 1330 px inner height; nav + Chart Maps head + pinned tabs + board head ≈ 236 px → ≈ 1094 px for 3 rows + 2 gaps → ≈ 356 px per tile):

  | Quantity | Arithmetic | Result |
  |---|---|---|
  | Tile width | (2560 − 32 − 2 × 13) / 3 − 22 | ≈ 812 px |
  | 3-min / 5-min width | half the tile less the 8 px gap | ≈ 402 px |
  | 1-min height | 812 × 120 / 620 | ≈ 157 px |
  | 3-min / 5-min height | 402 × 180 / 620 | ≈ 117 px |
  | Tile height | 19 pad + 24 head + 2 × 14 captions + 157 + 117 + 8 gap | ≈ **353 px ≤ 356** |

  If the measured screen overflows, the heights are HIS CALL #10, not the executor's to change.

## The look: the replay video

- **Palette provenance.** `eod-audits/replays/replay_gif.py:576-581` PALETTE: bg (13,17,23), grid (38,43,52), text (225,228,232), dim (135,142,152), up (38,186,104), down (235,72,72). The 9 EMA is `#FACC15` and the 21 EMA is `#BE78FF` (`replay_gif.py:579`). Both lines are 2 px, drawn over the candles (`replay_video.py:258-260`, `:339-350`).
- **`.ggw-dark`** sets `--surface`, `--bg-raised`, `--bg-sunken` and `--cm-card` to the replay background, and `--rule`, `--ink`, `--text-muted`, `--positive` and `--negative` to the replay colours. The chart-only tile therefore paints the replay panel.
- **`lib/chartMaps.ts` `EMA_BOLD`** holds the two colours and widths. It is the one source for the chart and the legend swatches.

## PatternChart props: each default draws exactly as before

PatternChart draws every Chart Maps card, so all three props are optional and change nothing when they are left out. Before merging, 182 renders of every fixture tile were compared with the props absent, hover included: the HTML was byte-identical before and after.

- **`chartOnly`** — a plain `div.cm-tile.cm-tile-chart-only`, never a router link, so there is no SEPA link anywhere on the board. The head, rungs, footer and ▸ more are skipped. The svg, hover crosshair and markers stay.
- **`emaStyle="bold"`** — the `ema9` / `ema21` curves are drawn **after the candles** (21 first, then 9 on top) in `EMA_BOLD`, with `vector-effect: non-scaling-stroke` and opacity 1. The 9/21 cross diamonds are taken out of the marker pass and drawn in their own group after the bold EMAs, so a cross is never hidden under the lines. Other curves keep their look and their place under the candles.
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
