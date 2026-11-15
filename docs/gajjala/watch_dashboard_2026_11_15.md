# 👀 Gajjala's Watch — owner list, routes, GET payload (2026-11-15)

**Package:** `backend/chart_maps/gajjala_watch/` — `store.py`, `api.py`, `payload.py` (this doc); the minute loop, tiles
and the cross push are in `watch_cross_alerts_2026_11_15.md`; the board in `watch_frontend_2026_11_15.md`.

## His words (verbatim)

> "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove tickers from the
> dashboard.
>
> When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear distinction or may be a
> brighter and thicker 21 EMA and 9 EMA, from the videos I notice that when ever 9 EMA crosses over 21 EMA on uptrend is
> where the bullish momentum started I need alerts on these from 1 min to I can be ready... I think the cross over is
> slow but once it picks up its very rapid.."
>
> "I have a 27 inch monitor I wanna fit 3x3 tikers on watch at any given time on this tashboard"
>
> "Any chart I view make sure you are showing me from 4 AM for historical behaviour and also the right side with gaps to
> see where it might go"

**UNMEASURED.** Nothing has measured what follows a 9/21 EMA cross on any frame. A cross is information, not an entry.

## The list (`store.py`)

- ONE doc in `gajjala_watch_list`: `{_id: "owner", symbols: [...], updated_at, by}`. `colls.owner_symbols` is the one
  reader for the loop and the payload; `add` / `remove` read the doc themselves so a failed read answers `error` and
  never writes an empty list over his names.
- `normalize(raw)` = `strip().upper()` then `supply_demand.accumulation_changes._TICKER_SHAPE` (imported).
- `add` → `added` (appended at the END — his order) · `already` · `full` · `bad_symbol` · `error`.
  `full` is REFUSED at `C.MAX_SYMBOLS` (12, HIS CALL #1); Signal Lab's silent drop of the oldest is NOT copied.
- `remove` → `removed` · `absent` (also for a string that is not a ticker) · `error`.
- Never raises. A removed name's tile doc and claims stay (audit); the board shows listed names only.

## Routes (`api.py`, included once in `backend/main.py` next to the Long Term router)

| Route | Gate | Answer |
|---|---|---|
| `GET /chart-maps/gajjala-watch[?symbols=A,B]` | `maybe_current_user` → `_is_owner` (`ollama_chat.api.is_primary_admin`) | Anyone else, no email, or a direct call that receives the `Depends` OBJECT: exactly `{state: "owner_only", reason, title}`, HTTP 200, **nothing read**. Owner: the board below. |
| `POST /chart-maps/gajjala-watch/symbols/{symbol}` | `require_primary_admin` (404 before the handler) | `store.add` → `{state, symbols, symbol, text}`; the build child on `added` only (below). |
| `DELETE /chart-maps/gajjala-watch/symbols/{symbol}` | the same | `store.remove` → `{state, symbols, symbol, text}`. |

**Encode off the loop (C2.4).** The owner's body is built, NaN-scrubbed (`growth.api._scrub`), JSON-encoded and gzipped
(level 6) inside ONE `asyncio.to_thread` — the `/sepa/scan` pattern. A request that accepts gzip gets the pre-encoded
bytes with `Content-Encoding: gzip` + `Vary: Accept-Encoding` (GZipMiddleware passes it untouched); otherwise plain
JSON. Measured before the build: a full 12-name board is ≈ 2.37 MB raw / 593 KB gzip.

**`?symbols=`** is the pending poll: names are normalized, and only LISTED names are served — an unlisted one is dropped
and its tile doc is never read. The head keys are still served.

**The single-flight build child (C2.5).** On `added`, and only when `colls.loop_reads_soon(now)` is False (the minute
loop will not read the new name within about a minute — out of the pass window, a closed day, or past the extended
close), the API asks for ONE `python -m chart_maps.gajjala_watch.loop --build` child (`on_demand._spawn`). Module
`_LOCK` + `_BUILD["proc"]`: while that child is alive (`on_demand._alive`) a second add spawns nothing — the alive child
re-reads the list before it exits. A raising spawn logs one line and the POST still answers `added`. At most one build
child is alive in the API container.

The admin email never appears in an answer; the frontend never compares emails.

## The owner's GET payload (`payload.build`)

Stored docs only — never a bar fetch: the list (one `find_one`), the tile docs of the listed names (ONE
`find({_id: {$in: names}})`), the loop state doc (one `find_one`, `_id: "latest"`), today's pushed claims (ONE
`find({date: session, state: "cross_pushed"})`). Every read is fenced; no database or an unreadable list answers `state: "error"` + the served reason (never the empty words); the loop and build child keep the fail-soft `[]`.

Head: `title`, `session`, `is_today`, `in_window`, `refresh_sec` (= `GG1M_CADENCE_SEC` in the window, else 0),
`next_window_sec` (out of the window only: seconds to the next market day's `PASS_OPEN_ET` 04:00 — today's when it is a
market day before 04:00; Sunday 12:00 → 57,600 s), `pending_poll_sec` / `pending_wait_max_sec` (=
`ON_DEMAND_POLL_SEC` / `ON_DEMAND_WAIT_MAX_SEC`, **only while a row is pending**), `max_symbols`, `symbols` (his
order), `full`, `full_text`, `add_label`, `add_placeholder`, `remove_label`, `empty_text`, `pass`, `info`, `legend`,
`rows`.

- `pass` = `{at_et, text, stale}` from the loop state doc; `stale` = in the window and older than
  `GG1M_STALE_AFTER_SEC`; None when there is no state doc.
- `info` = `{honesty, push_text, uptrend_rule, push_mode, push_frames}` — served ONCE on the board, never per row or
  chart (C4.6). `push_text` / `uptrend_rule` come from `cross_alerts.rules_line()` / `build.uptrend_rule()`, imported
  lazily; a failure serves None and the board still answers.

### Row states

Rows follow HIS list order — the server never reorders (not by cross, not by price).

| Tile doc | `state` | `stale` | `text` |
|---|---|---|---|
| none | `pending` | false | in window "⏳ first read at the next minute"; out "⏳ reading {SYM}'s last session" |
| has `frames`, status `loaded` | `ok` | false | None |
| has `frames`, last read `failed` | `ok` | **true** | "⚠️ the {HH:MM} read failed — showing the {as_of} bars" (the last good charts stay, C1.2) |
| has `frames`, last read `over_budget` | `ok` | **true** | "⚠️ not read this minute (time budget) — showing the {as_of} bars" |
| has `frames`, last read `no_prints` / `no_bars` | `ok` | **true** | that status's sentence |
| no `frames`, `no_prints` | `no_prints` | false | today "No prints yet today for {SYM} — the chart starts at its first print"; past "No prints for {SYM} on {session}" — never "check the ticker" (C1.6) |
| no `frames`, `no_bars` | `no_bars` | false | "No minute bars for {SYM} on {session} or the session before — check the ticker" |
| no `frames`, `failed` (or an unknown status) | `failed` | false | "The minute bars could not be read — the next minute tries again" |
| no `frames`, `over_budget` | `over_budget` | false | "Not read this minute (time budget) — the next minute tries again" |

`as_of_et` = the doc's `loaded_at` in ET ("HH:MM" today, "YYYY-MM-DD HH:MM" otherwise). `from_session` = the doc's
session when it is not the board's.

Each `ok` row serves three frames in `C.FRAMES` order (1m, 3m, 5m):
`{tf, label, tile: {symbol, href: "", bars, curves, markers, lines: [], bands: [], stats: [], why: "", vol_avg}, axis,
ema_cross | None, uptrend: {ok, short}, held: {text} | None}`. `href` is empty: no SEPA link anywhere.

- **`held` (C4.4)** is served only when the doc's `held[tf].bar_t` equals that frame's latest drawn UP cross (the stored
  `ema_cross.crosses` — the diamonds) and the reason is not `pushed`; a stale `bar_t` serves nothing. Words: off · missed
  fetch (never sent late) · market closed · pre-market · first {NO_TRADE_AFTER_OPEN_MIN} minutes · after the extended
  close · under GG's {K11_MIN_SESSION_VOLUME:,} session-volume floor · not a K5 uptrend · alert store down · no device ·
  send failed.
- **`rang`** = today's claims of the name in `gajjala_watch_alerts` with state `cross_pushed` (= the ➖ Fade cross's
  `FADE_CROSS_STATES[1]`); a `cross_claimed` / `cross_no_target` / `cross_failed` claim is not a chip.

Every served word is a constant in `payload.py`; every number inside a word is a `{}` field filled from its constant at
call time (a source guard pins it).

## Tests

`backend/tests/test_gajjala_watch_store_2026_11_15.py`, `backend/tests/test_gajjala_watch_api_2026_11_15.py`
(negatives: non-owner reads nothing, 404 writes with no spawn, single-flight, unlisted `?symbols=` never read, no
reorder, stale / pushed `held` not served, rule sentences once, admin email absent, no typed digit in words).
