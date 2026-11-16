# ➕/➖ Watch on every card (2026-11-15)

Ajay, verbatim: "can you add an add to watch list button on all the stocks to move them and also remove button from watch
list too."

## What it does
- Every Chart Maps card (PatternChart's action row: 🚩 Gajjala 5-min / 1-min / 🧪, 🥇 Luk, and every tile board) carries
  one button. Off the list it reads **➕ Watch**; on 👀 Gajjala's Watch it turns green and reads **➖ Watch**.
- Click ➕ = the existing owner route `POST /chart-maps/gajjala-watch/symbols/{symbol}` (appends at the END, his order;
  the cap is `constants.MAX_SYMBOLS`, refused when full). Click ➖ = `DELETE` on the same route.
- At the cap ➕ is disabled and its title is the served full sentence; ➖ still works.
- The 👀 board's own Add box and Remove buttons are unchanged; a write there refreshes the card buttons' list.

## Wiring
- `GET /chart-maps/gajjala-watch/symbols` (new, `api.gajjala_watch_symbols`): the owner's names only —
  `payload.list_payload` → `{state: "ok", symbols, max, full, full_text, labels}`. Anyone else: exactly `owner_only`
  and nothing is read. A failing read answers `error` — never an empty list (that would offer ➕ on a name already
  watched). Read off the event loop (`asyncio.to_thread`).
- FE: `lib/ggWatchList.ts` = ONE store per page (one GET shared by every card, `useSyncExternalStore`); the list moves
  only on the server's answer, then re-reads (so `full` is always served, never guessed). `components/GgWatchButton.tsx`
  renders the served words; the card sits inside a `<Link>` so the click is `preventDefault` + `stopPropagation`.
- Owner only: the button renders nothing for anyone else (owner_only / error / failed fetch).

## Not changed
No gate, push, sort, scan or alert. Adding a name starts the 👀 Watch's own minute read and its own 1-min up-cross push
exactly as adding it in the 👀 Add box does today (that push's open HIS CALLs live in the 👀 Watch docs).

## Tests
`backend/tests/test_gajjala_watch_card_button_2026_11_15.py` (owner / non-owner / Depends object / failing read /
cap / round trip), `frontend/src/components/GgWatchButton.test.tsx` (served words, one GET, no link bubbling, never
optimistic, failed write, cap). The route-count pin in `test_gajjala_watch_api_2026_11_15.py` was WIDENED by one.

## Note
The cards already carry **+ Signals** (the ⚡ Signals watchlist, 2026-09-07). The two buttons sit side by side; which
one he wants kept is his call.
