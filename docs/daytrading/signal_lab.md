# Signal Lab — 1-minute BUY/SELL tags on user-added tickers (2026-09-01)

> Ajay: "calculate entries with a buy or sell indicator on a stock ticker I
> add to a new page ... interface like GainzAlgo ... same concepts from what
> we build with ORB, Liquidity grab, BOS ... custom tickers on demand like
> the session tab but more real time feedback of buy signals and sell
> signals on 1 mins candles."

## What it is

`/signal-lab` (feature `signal-lab`, owner-on via catalog v22): add up to 12
tickers; each renders the last session's 1-minute candles with signal
markers, the latest entry with stop/target, and an event feed. Polls every
45s while any session (premarket/regular/afterhours) is on; still when
closed. Watchlist persists per user in Mongo (`signal_lab_watchlist`) with a
localStorage fallback.

## The engine (backend/daytrading/signal_lab.py)

Events per closed 1-minute bar, oldest-first — ALL uncited convention
(SMC = ICT lineage, ORB = the app's gap-and-go heuristic; no book cites):

| kind | fires when |
|------|------------|
| `orb_up` / `orb_dn` | first close beyond a COMPLETE 15-minute opening range (once each) |
| `sweep` | wick through a confirmed swing, close back inside — one per level per session, swing within `SWEEP_LOOKBACK=60` bars |
| `bos` / `choch` | close beyond the most recent opposing confirmed swing (deduped per swing) |
| `buy` / `sell` | the five-step composite: sweep then opposite structure break within 30 bars → entry at that close, stop at the trap wick, target 2R |

## The non-repaint contract (the point of the module)

GainzAlgo's headline claim, made checkable. `smc.liquidity_sweeps` /
`structure_breaks` recomputed on a full frame will match a bar against a
swing confirmed AFTER it (a swing at j exists only once bar j+3 closes) —
replayed live that is time travel. The lab runs its own walk over
`smc.swing_points` with the confirmation lag enforced, so the event stream
is **prefix-stable**: `events(frame[:k]) == [e for e in events(frame) if
e.i < k]`. Locked by `test_signal_lab.py::test_prefix_stability`. The
sweep-density lesson (first smoke: TSLA printed 90 "sweeps" in 2 hours
before the per-level dedupe + lookback) is locked by
`test_one_trap_per_level_per_session` / `test_stale_swing_is_not_liquidity`.

## Presentation

GainzAlgo UI conventions, our math: BUY tag prints UNDER its candle, SELL
above it (PatternChart `markers` with `kind` + `price`); sweep/BOS/CHoCH as
small glyphs; stop/target lines from the latest composite. GainzAlgo's own
formula is paid/closed and none of it is used.

## Endpoints

- `GET /day/signal-lab/board?symbols=A,B,C`
- `GET/POST/DELETE /day/signal-lab/watchlist[/{symbol}]` (user-scoped via
  `current_user_email`)

## 2026-09-07 — one watchlist, one click from every board

Ajay: *"Give me options in Catalyst promo tab list for add something to signals. Also same
from Demand and deep demand. One click and add to signals tab. Same from Gabbars and strong
VCP and from Quick Bounce.. So I can add it to signals — signals is like my watch list."*

- `frontend/src/hooks/useSignalWatchlist.ts` — the ONE store: server list first
  (`GET/POST/DELETE /day/signal-lab/watchlist`, per user), localStorage `signal-lab-symbols`
  as the offline mirror, `held` from the portfolio merge, `MAX_SYMBOLS = 12` (matches
  `daytrading/signal_lab.MAX_SYMBOLS`; a 13th add drops the oldest on both sides).
- `SignalWatchButton` — `+ Signals` / `✓ Signals` / `💼 Signals` (held: static). Mounted on
  every Chart Maps card (`PatternChart`, beside TV — so every tile board) and in the promo
  list's ticker cell (`PromoCircuit.SymCell`, compact). The click never bubbles into the
  card's link.
- `SignalLabBoard` renders the same store, so a click on a Deep Demand card is on the
  Signals tab the moment it opens. No backend change.
- Tests: `useSignalWatchlist.test.ts`, `SignalWatchButton.test.tsx`, `PatternChart.test.tsx`
  (+ negative held), `PromoCircuit.test.tsx`, `SignalLabBoard.test.tsx`; contract "Every
  board card and the promo list carry the one-click + Signals button".

## 2026-09-10 — the ticker page carries it too, and the cap stops lying

Ajay: *"Add a signals button in individual ticket page, I am using it as a watch list page."*

- `SignalWatchButton` gained an optional **`chrome`** prop (default `WATCH_CHROME_CARD =
  'cm-tv'`, so the board and promo mounts are byte-identical to before). It **replaces** the
  look class, it does not append: `.cm-tv` (styles.css:11573) sits BELOW `.sepa-btn--ghost`
  (3641) and both are single-class, so an appended chrome loses the cascade and the button
  renders as a 10px chip beside full-size siblings. `cm-watch` is never swappable — it is the
  sole anchor for `.cm-watch.is-on` (green, already on the list) and `.cm-watch.is-held`
  (dimmed). **Both branches take the chrome**; the held state is a `<span>`, not the button.
- Mounted first in `.sepa-candidate-page__head-actions` on `pages/SepaCandidate.tsx` with
  `chrome="sepa-btn sepa-btn--ghost"`. It LEADS the cluster because keeping the name is the
  verb that page is open for; 🔔 Quick alerts / ✎ Custom level / ↻ Re-scan act on it instead.
- **Two different lists on one page.** The Setup tab's `+ Add to watchlist` writes the SEPA
  entry/stop plan (`POST /sepa/watchlist`, rendered at `/watchlist`). The head-action
  `+ Signals` writes `signal_lab_watchlist`. Neither reads the other; the labels are the only
  thing keeping them apart, so do not rename either one to "watchlist".

### Bug found while wiring it: the cap counted names it does not cap

`merge_holdings` returns `symbols` = watchlist ∪ portfolio, **uncapped** — only the *stored*
watchlist is capped at `MAX_SYMBOLS`. The client computed `full` from that merged length, so a
user with a portfolio saw "the list holds 12, so the oldest name drops off" long before
anything would actually be evicted. Ajay watches 5 names and holds 5, which already merges to
7 of a 12-name budget he has barely touched.

The client cannot recover the real count on its own: subtracting `held` undercounts every name
that is both watched and held (ATEX, DASH and NTSK are all three, for him). So the **server now
reports it**:

- `merge_holdings` → `+ watch_n` (size of the stored list) and `+ max_symbols`.
- `useSignalWatchlist` → `watchN` + `watchCount(s)`, and `full: watchCount(s) >= MAX_SYMBOLS`.
  `watchN` is `null` until the server answers and on any pre-2026-09-10 response, where
  `watchCount` falls back to the merged length — the old behaviour, unchanged.
- Optimistic add/remove adjust `watchN` so the mirror stays self-consistent across the round
  trip and across a failed POST; the server's value overwrites it on every response.

**The 12-name cap itself is unchanged.** A 13th add still silently drops the oldest on both
sides — that is pre-existing and deliberate, and it is what the warning is for.

- Tests: `SignalWatchButton.test.tsx` (12) — default chrome pinned to `cm-tv cm-watch`, custom
  chrome keeps `cm-watch` in both the button and held branches, `watchCount` fallback, and the
  NEGATIVE "a big portfolio does not make the list look full". `tests/test_signal_lab_holdings.py`
  (7) — `watch_n` vs the merged length, the both-watched-and-held case that defeats subtraction,
  dedupe/blank safety, and 20 held names against an empty watchlist.
- Contract: "The ticker page carries the + Signals button, sized like its siblings (2026-09-10)"
  — pins the mount inside the cluster, that `chrome` replaces rather than appends, that neither
  branch drops `cm-watch`, that `.cm-watch.is-on` / `.is-held` still exist in `styles.css`
  (jsdom loads no stylesheets, so no render test can catch that), and that `full` comes from
  `watchCount`.
