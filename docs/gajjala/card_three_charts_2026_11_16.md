# 🚩 Gajjala card → ⤢ three charts (15-min / 5-min / 1-min) + a separate "SEPA page" link (2026-11-16)

## 2026-11-18 (later) — a 1-min chart for ANY card name, built on demand

Ajay, 2026-11-18: "Also I need to keep 1 min charts when I am viewing specific stock". When neither the 1-minute page's doc nor a same-session 👀 Watch tile has 1-minute bars, `card_frames.py` builds the 1-min frame for that ONE name with the Watch's own builder (`gajjala_watch.build.frames` + `build.tile_update`, the update read, never written — no tile doc, no Watch seat): ONE minute fetch of today per ⤢ GET (prior day from the 1-minute day cache), never on a board load. A fetch fault / no bar keeps the served words below; 15-min / 5-min unchanged. Every frame now serves `source` = {kind: gajjala | gajjala_1m | watch | on_demand, at}; the FE ignores it. This builds HIS CALL #14 option (a) of `docs/gajjala/retire_1m_page_2026_11_18.md`. Tests: `backend/tests/test_gajjala_card_frames_on_demand_2026_11_18.py`. UNMEASURED.

## 2026-11-18 — the 1-min frame reads the 👀 Watch's tile while the 1-minute page is retired

Ajay, 2026-11-18: "This is good info stop 1 min tab it was a good experiment" and "But keep the one min chart in the
watch list I still want them". The 1-minute page's pass (the source of the 1-min row in the table below) no longer runs,
so `card_frames.py` fills an EMPTY 1-min frame from the 👀 Watch's stored 1-minute tile (`gajjala_watch_tiles`,
`frames["1m"]`) of the SAME session — ONE stored read, no fetch, no write; stamp = the Watch doc's `at`, stale through
`GG1M_STALE_AFTER_SEC` by name. Names on the Watch (his list + the 🤖 auto names) draw a 1-minute chart; a name not on
it prints served words ("… the 1-minute page retired 2026-11-18 by your call; a card's 1-minute view now comes from the
👀 Gajjala's Watch, and SYM is not on it"). A prior-session Watch tile never draws as today. The 15-min and 5-min frames
are unchanged. Reversible: when the page runs again, its own 1-minute read doc leads by itself. A fresh fetch per card
tap for the other names = HIS CALL #14 in `docs/gajjala/retire_1m_page_2026_11_18.md`. UNMEASURED.

Ajay, verbatim:
- "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart extension like in the Watch
  list... Also put a SEPA page link for it separaetely on the card I I want to but default its 3 chart extension with
  1 min, 3 min and 5 mins"
- "Actually instead of 3 mins make it 15 mins timeframe"

## What changed (display only — no rule, gate, push, order or trade changed)
- **A click on any charted 🚩 card opens the 👀 Watch's own full-screen view** for that stock — on all three boards
  (🚩 5-min `tab=gajjala`, the 1-minute page `tab=gajjala_1m`, 🧪 Audited `tab=gajjala_audited`) and every sub that
  draws cards (🚩 💋 ➖ 🌀 🎾 ☀️ 🌙 🧠 …). The view is the Watch's component, moved into
  `components/GajjalaWatchTile.tsx` and reused (`GgwStretch kind="card"`) — never a second implementation.
- **Frames: 15-min, 5-min, 1-min**, stacked big → small top to bottom (`GGC_STRETCH_ORDER`, the Watch's convention —
  HIS CALL #1 below). The 👀 Watch's own ⤢ keeps 5-min / 3-min / 1-min (`GGW_STRETCH_ORDER`, unchanged).
- **"SEPA page"** — a separate link, first in the card's action row, opens the stock page with the card's served frame
  (the served `tile.href`, `&tf=` kept). Enter on that link (or on Yahoo ↗ / ➕ Watch / ▸ more) does that control's own
  thing; only Enter / Space on the card itself opens the view.
- ◀ ▶ and ← → step through the cards the board DRAWS (its order, the 💋 toggle's hidden cards skipped), wrapping; ⤡,
  Esc or a click on the dark margin closes the view; it closes by itself when its stock leaves the drawn cards (a sub
  change, a filter, a pass that drops the name) and never re-opens on its own.
- Bar-less ☀️ / 🌙 mover tiles keep their stock-page Link (no view — HIS CALL #7).

## Where each frame comes from (zero provider fetches — the docs the passes ALREADY store)
ONE read-only GET `/chart-maps/gajjala/frames/{symbol}` (backend `chart_maps/gajjala/card_frames.py`), no owner gate
(the same audience as the cards — HIS CALL #4).

| Frame | Source doc | Bars | Stamp + ⚠️ stale rule |
|---|---|---|---|
| 15-min | the 🚩 5-min pass's read doc (GG5) — `bars15` | today's closed 15-min bars from 04:00 ET; 9/21 EMA warmed by the prior session | GG5 doc `at`; stale after `STALE_AFTER_SEC` |
| 5-min | the GG5 read doc — `bars5` (no GG5 doc → the 1-minute loop's own `bars5`, its stamp) | today's closed 5-min bars from 04:00 ET | GG5 doc `at` (or GG1's); `STALE_AFTER_SEC` (or `GG1M_STALE_AFTER_SEC`) |
| 1-min | the 1-minute loop's read doc (GG1) — `bars1` | **the last 192 one-minute bars that printed** (`GG1M_TILE_BARS_MAX`) — a sparse name spans longer than 192 minutes (AIMD on 11-16: 15:41 → 19:58) | GG1 doc `at`; stale after `GG1M_STALE_AFTER_SEC` |

- The 1-minute loop reads at most `GG1M_MAX_NAMES` (60) of the 🚩 list. A card outside it has no 1-minute doc → its
  1-min frame prints the served words ("No 1-minute bars stored for SYM this session yet — a pass has to read it
  first"), never an empty chart. On 11-16, **41 % of the cards (58 of 141) had no 1-minute doc** (HIS CALL #3).
- Each frame prints ITS OWN source stamp under its chart; a stale frame prints it with the Watch's `⚠️ ` and carries
  no live forming bar. The thresholds are the existing constants, read by name (`V.stale_after_sec(v)` →
  `STALE_AFTER_SEC` for the 5-min pass, `GG1M_STALE_AFTER_SEC` for the 1-minute loop) — no new number. A name that
  left the 1-minute loop early shows a ⚠️ 1-min frame while its 15-min and 5-min frames stay fresh.
- The view's head line is the card's served plan line (HIS CALL #9); the row stamp is the card's own (GG5) doc's.
- 15-min bars early in the session (closed bars from 04:00, `BAR_SETTLE_SEC` after each close): 06:00 → 8, 08:00 → 16,
  09:30 → 22, 16:00 → 48, 20:00 → 64. The 9/21 EMA is warm from today's first bar (the prior session warms it); a new
  listing with a short prior session gets no curve on that frame (a gap, never a guess).
- **Axis end from ALL three frames' bars**: the served 04:00 axis ends at the extended close as soon as ANY frame has a
  bar after 16:00, so no bar of any frame is drawn past the right edge (on 11-16, 19 of 83 names had 15-min bars past
  their last 1-minute bar).
- The card's served lines and bands are drawn on every frame; its markers (A+ / cross) only on the frame the card drew
  — mapped by date, so a 🎾 card's prior-session marks drop (information lost, never a wrong mark — HIS CALL #11).
- Live: the forming bar rides the board's EXISTING stream (no new live interest), the EMA tip seeded from the stored
  6-dp curve tail (the Watch's `GGW_LIVE_EMA_TIP`) — HIS CALL #5.
- **Re-read cadence = the board's own poll**: the open view re-GETs only when the board's own GET lands (`boardSeq`)
  or the open stock changes — never on a quotes batch (≈ 1/s in RTH) — HIS CALL #10.

## Tests
- `frontend/src/components/GajjalaBoard.card_view.test.tsx` — a card click opens exactly 15m / 5m / 1m (no 3m); ONE
  frames GET per open, five quotes batches → still one, a landed board poll → two; no GET with the view closed; the
  `onOpenView` reference is the SAME function across re-renders; ◀ ▶ / ← → step in drawn order with wrap and the GET
  follows; Esc / ⤡ close; one card → no ◀ ▶; the view closes when the stock leaves the board; bar-less tiles keep their
  Link; lines/bands on every frame, markers on the card's frame only; a stale 1-min frame prints `⚠️ HH:MM` and gets no
  forming bar while 15m / 5m do; another variant's batch changes nothing; no live POST from the view; the three
  variants (`gajjala`, `gajjala_1m`, `gajjala_audited`) — each: open / Esc, no GET while closed, ▶ step + GET follows,
  ⤡ close and no GET after it (2026-11-17 refix); a 430 px phone stub → one column, phone heights. The real-browser
  430 px measurement is the main session's, after deploy (spec §5.5).
- `frontend/src/components/GgCardView.test.tsx` — the real charts: three svgs; an empty frame prints the served words
  and no svg; served `text` in the head; a failed GET prints the one FE sentence; a served `error` prints its reason.
- Backend: `backend/tests/test_gajjala_card_frames_2026_11_16.py` (the frames GET). FE lib / component:
  `GajjalaWatchTile.test.tsx`, `gajjalaCardView.test.ts`, `ggwLive.cardview.test.ts`, `PatternChart.openView.test.tsx`.

UNMEASURED — a chart view is information, not an entry.

## HIS CALLs (defaults built; none decided here)
1. Frame order: built 15-min / 5-min / 1-min top → bottom (the Watch's big → small). He listed "1 min, 5 min, 15 min"
   — the opposite order. Reversing is one constant (`GGC_STRETCH_ORDER`).
2. Whether the 👀 Watch's own ⤢ also moves 3-min → 15-min — NOT changed.
3. 1-minute frame: the stored card bars (the last 192 that printed; names within the 1-minute page's 60 — 41 % of
   11-16's cards had none) vs an owner-gated on-demand fetch of the full 04:00 day — the fetch is NOT built.
4. Audience: the frames GET has no owner gate (stored docs only). Owner-only like the Watch = his word.
5. Live forming bar in the view: ON (the board's existing stream), EMA tip ON; OFF on a stale frame.
6. The link's label "SEPA page" and its place — first in the card's action row.
7. Bar-less ☀️ / 🌙 mover tiles keep their Link (no view).
8. 🥇 Luk's cards are not Gajjala — unchanged.
9. The view's head line = the card's served plan line.
10. Re-read cadence of an open view = the board's own poll (no extra timer; the Watch re-GETs every minute).
11. Markers only on the frame the card drew; the other two frames carry lines / bands only.
12. Stale words on a frame = its stamp with `⚠️ `; the threshold is that source's existing constant
    (`STALE_AFTER_SEC` 900 s, `GG1M_STALE_AFTER_SEC` 300 s). A longer sentence, or a different threshold (a gate
    change), = his word.

## 2026-11-18 — the tiles ARE the board

Ajay 2026-11-18: "I need the watch list kinda chart formant view video view as default here too from the tabs pages" → his
pick "Tab cards as Watch tiles". The 🚩 5-min and 🧪 Audited card grids now draw, by default, as the 👀 Watch does: each
charted card's chart slot is the Watch `Tile` over this SAME frames GET (`GGC_PATH/{symbol}`), stacked 15m / 5m / 1m in
`GGC_STRETCH_ORDER`, with the card's overlay through `ggcRow(card, p, look, { plan: false })` (the plan line prints once,
in the card's CardExtras). ⤢ on a tile opens this view unchanged. The GET is asked only for the cards on screen, once per
landed board read; the 1-min frame on a tile is the same served frame (the Watch's stored tile for names on the Watch,
else the retired words — shrunk to their height on the board tile only). `NO_FRAMES` moved to
`lib/gajjalaCardView.GGC_NO_FRAMES` (one definition, GgCardView reuses it). A toggle (`👀 Watch layout`, per device) brings
the small cards back. Details: `docs/gajjala/card_grid_watch_layout_2026_11_18.md`.

**2026-11-23 — 🎾 `?card=squeeze`.** An optional `card` param on this GET (asked only by a 🎾 card in the Watch layout) serves the Watch order, the 9/21 cross markers + K5 on every frame and the 5-min prior tail on a lead axis; without it this payload is byte-identical. Details: `docs/gajjala/card_frames_squeeze_card_2026_11_23.md`.
