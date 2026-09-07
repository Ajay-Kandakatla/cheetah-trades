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
