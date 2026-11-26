# 📅 Runners on one continuous chart — backend (2026-11-26)

Spec: `runcharts` rev 2, §3.1-§3.5, package `be-chart`. The front end has its own doc
(`runners_continuous_chart_frontend_2026_11_26.md`).

## The ask, verbatim

Ajay 2026-11-26: "I want you to have continous charts for previous day runners we have some examples with traderview
charts with couple of indicators can you set that up? I wanna able to horizontal scroll tp check continuity like he does"

**GG tag: 🟡 display.** It supports GG's own "Multi-Day Movers" characteristic (`verified_rules.json` topics[10]). No
decision changes. VWAP is not GG's, so it is built and left OFF.

## Endpoint

`GET /chart-maps/gajjala-watch/runners/chart/{symbol}?tf=1m|5m|15m` (`C.API_RUNCHART_PATH`).

- **Owner only.** The route checks `_is_owner`. Anyone else, or a direct call that receives the `Depends` object, gets
  exactly `owner_only_payload()` with HTTP 200, and nothing is read. A request with no identity at all gets the app
  middleware's 401.
- **Built off the event loop.** The body is built, scrubbed (NaN becomes null) and JSON-encoded inside ONE
  `asyncio.to_thread` (`api._runchart_body`). It never raises: a fault answers state `error` with
  `RUNCHART_FAULT_TEXT`.
- **No session-count parameter.** An unknown query key such as `?sessions=99` is ignored and changes nothing.
- **Engine:** `chart_maps/gajjala_watch/runchart.py`. It only chooses days and calls the house engines:
  - `daytrading.data.load_intraday`, with the chart's OWN breaker from `new_breaker`;
  - `prev_market_day` and `tab.session_for`;
  - `resample_ohlcv`, `bars.closed_only`, `bars.build_frame` and `bars.tile_payload`;
  - `alerts._closes`, `drop10_tab.fetch_splits_strict` and `runners.ran_for`;
  - `build.name_vwap` and `vwap.frame_values`, used only when VWAP is on.

## The EMA seeding (word for word, §3.3)

- 9 / 21 EMA = `orderflow.signals.ema` through `bars.build_frame` — EMA_t = α·close_t + (1 − α)·EMA_{t−1}, α = 2/(n + 1),
  the first value = the first close (the thinkorswim `MovAvgExponential` formula, §1.7).
- It runs over EVERY closed bar of the frame handed in — the seed session(s) + the drawn sessions, pre-market, regular and
  after-hours — in time order. It is NOT restarted at a session, at 09:30, or at the overnight gap.
- `RUNCHART_SEED_SESSIONS` (1) session before the first drawn one is loaded only to warm it: at 5-minute bars a full
  session is 192 bars, so the first drawn bar's 21 EMA carries (1 − 2/22)^192 ≈ 1e-8 of the seed — nil.
- The first `period − 1` bars of the LOADED frame are a gap, never a guess (`bars._masked_ema`); a thin name with fewer
  bars than that before the first drawn bar starts its line late.
- After a split cut (§3.2 #8) the frame starts at the cut: the seed session may be gone and the line then starts late.
  When every earlier day was read after the split nothing is cut and the line is continuous across it.
- The values at a bar can differ in the last decimals from the 🚩 card's (which runs over two sessions): more history here.
- A bar is drawn at its START (`chart_x`); the cards and the 👀 Watch stamp the same bar at its CLOSE. The
  5-minute bar this chart puts at 10:00 is the card's "10:05". Same bar, same EMA value.

## Constants (`gajjala_watch/constants.py`, one dated block)

| Constant | Value | Provenance |
|---|---|---|
| `RUNCHART_FRAMES` | `FRAMES` (1m / 5m / 15m) | the Watch's own rules, by name |
| `RUNCHART_DEFAULT_TF` | `GC.RUN_BASE_FRAME` = "5m" | GG T1 "I concluded on the five minute" |
| `RUNCHART_SESSIONS` | 5 | HIS CALL #1: his thinkorswim "5 D 5m"; 11-23 "duration to 5 days" |
| `RUNCHART_SEED_SESSIONS` | 1 | MINE (HIS CALL #11): EMA / volume-average warm-up only |
| `RUNCHART_MAX_BARS` | 5000 | TRANSPORT, MINE: 5 × 960 one-minute bars fits |
| `RUNCHART_BUDGET_SEC` | 12 | TRANSPORT, MINE: wall budget of one build's day loads |
| `RUNCHART_MEMO_SEC` | 60 | TRANSPORT, MINE: live-day re-read AND the chart's refresh while open |
| `RUNCHART_MEMO_SLACK_SEC` | 5 | TRANSPORT, MINE: a live read is reused only while younger than 55 s |
| `RUNCHART_MEMO_MAX` | 24 | TRANSPORT, MINE: names whose days are held |
| `RUNCHART_BUILT_MAX` | 6 | TRANSPORT, MINE: served payloads held |
| `RUNCHART_WAIT_SEC` | 4 | TRANSPORT, MINE: wait for the same name's read in flight, then `busy` |
| `RUNCHART_BUSY_RETRY_SEC` | 2 | TRANSPORT, MINE: served on `busy` |
| `RUNCHART_SPLIT_RETRY_SEC` | = `RUNCHART_MEMO_SEC` | TRANSPORT: no split check for this long after one raised |
| `RUNCHART_SPLIT_SAME_DAY_OK` | False | HIS CALL #7 |
| `RUNCHART_VIEW_SESSIONS` / `_PHONE` / `RUNCHART_RIGHT_GAP_BARS` | 2 / 1 / 12 | DRAWING, MINE (HIS CALL #8) |
| `RUNCHART_VWAP_ON` | False | HIS CALL #2 |

All the words (`RUNCHART_TITLE`, `_ASOF_TEXT`, `_EMPTY_TEXT`, `_ERROR_TEXT`, `_FAULT_TEXT`, `_BUSY_TEXT`, the split, failed,
budget and bar-cap texts, and `RUNCHART_HINT`) live in the same block. Every `{}` is filled when the payload is built,
from a constant read by name.

## What a cold open costs

These are the spec's measurements (§1.3 / §1.3b, not re-measured by this package).

- **Day loads.** A cold open makes at most `sessions + seed` = 6 day loads. Each one is a single cache read, or a single
  Massive call of about 0.3 s pooled.
- **Other reads.** There is one split check (its own 15 s timeout) and one small projected Mongo find for `cached_at`.
- **Nothing cached yet.** On 11-26, nobody's run day (11-25) was in `intraday_cache`.
- **Build time on the host.** Measured over 6 synthetic sessions with `…/scratchpad/runcharts/critic/timing.py`:

  | Frame | Bars | Build | JSON | gzip |
  |---|---|---|---|---|
  | 1-min | 4,800 | 261 ms | 684 KB | 146 KB |
  | 5-min | 960 | 55 ms | 139 KB | 32 KB |
  | 15-min | 320 | 21 ms | 46 KB | 12 KB |

- **Measured in a container, 2026-11-26 ~04:35 ET (market closed).** One throwaway api (`--cpus 2`, `--lifespan off`,
  so no poller, socket or outbox drain ran; :8001), with this branch's `gajjala_watch/` mounted read-only. Real Wed 11-25
  runners, wall time from `curl`:

  | Call | Bars | Wall | JSON | gzip |
  |---|---|---|---|---|
  | BGLC 5-min, cold | 142 | 2.52 s | 20 KB | — |
  | BGLC 5-min, again (held payload) | 142 | 0.004 s | 20 KB | — |
  | BGLC 1-min, frame change | 561 | 0.038 s | 74 KB | 20 KB |
  | NXAT 5-min, cold | 823 | 1.03 s | 114 KB | — |
  | NXAT 1-min, frame change | 3,243 | 0.16 s | 434 KB | 108 KB |
  | NXAT 15-min, frame change | 301 | 0.023 s | 44 KB | — |

  Four cold names at once (ALGS, LOOP, FCUV, POM): all `ok`, 0.85–2.07 s. One cold name twice at once (RADX): both
  `ok`, byte-identical, 0.61 s each. All 24 names on the 11-25 strip answered `ok` with only market days (no 11-21, 11-22
  or 11-26) and no `notes`: **no split case seen** — the split rule is still not seen on a live case. No identity → 401;
  another e-mail → `owner_only`. The api log printed no 429 and no fetch error. The loader logs no line for a fetch that
  succeeds, so "no second fetch" rests on the wall times (4–38 ms against ~0.3 s for one Massive call), not on a log line.

## Memo, gate, busy — in plain words

- **One module lock, for dicts only.** `_LOCK` guards the module's dicts and nothing else. It is never held across a
  provider call, a Mongo read, a wait, a split check or a payload build. A test checks this with a source scan and
  again at run time.
- **One read per name.** Each name has its own gate (`_GATES`). A second ask for the SAME name waits up to 4 s, then
  answers `busy` ("Still reading … asking again in 2 s"). It never borrows the "feed did not answer" sentence. Another
  name is never behind the gate.
- **Finished days are read once.** A completed day that answered `loaded` or `no_bars` is held for the process's
  current session (`_DAYS`). A thin runner's empty day is therefore not asked again. The live day is never held there.
- **The live day is re-read about once a minute.** Its last answered read (`_TODAY`) is reused only while younger than
  `MEMO − SLACK` (55 s). That way a 60 s refresh always gets a new read.
- **Bars count as closed when they were READ.** A bar counts as closed as of the moment its minutes were read, not the
  moment of the request. A reused read therefore never serves a bar whose last minute was still printing.
- **Failed days are retried on the next open.** A `failed` or `over_budget` day is stored nowhere. The next build asks
  for it again, and only for it. A payload that carries either note is never served from the memo.
- **An unchecked split is not held either (2026-11-26).** A payload built while the split check did not answer
  (`split_checked` False, note `split_unchecked`) is never stored in `_BUILT`. Reopening the same name and frame rebuilds
  it from the held days. Inside `RUNCHART_SPLIT_RETRY_SEC` nobody asks again. Past it the same name asks again, and the
  answered payload, with its cut, is held as usual.
- **Built charts are held briefly.** The served payload is held per (name, frame) in `_BUILT`, at most 6 of them.
  - **Reuse rule:** it is reused while the days, the clock state (live / not live) and the live read's age all still
    match.
  - **Frame change:** inside the live read's window it reads nothing, only rebuilds.
  - **Second open on a closed day:** it costs one dict read.
- **The chart has its own breaker.** After `_CB_TRIP_AFTER` (3) straight provider failures, every uncached day answers
  `failed` in milliseconds for `_CB_COOLDOWN_SEC` (60 s). This breaker is never the module's `_CB` and never the
  Watch's. Cached days still draw.
- **Least-recently-opened names are dropped.** Past `RUNCHART_MEMO_MAX` names, the least recently opened name's rows
  are dropped, and so is its gate when it is not held.

## The split rule (three cases)

A cached day keeps the share count of the day it was FETCHED, because Massive adjusts at fetch time. For the latest
split inside the window (oldest, newest]:

1. **Every earlier day was fetched after the split** (its `cached_at` ET date is after the execution date). Nothing is
   cut and every session is drawn. Note `split_adjusted`: "the sessions before it were read after it and are drawn on
   the new share count".
2. **Some earlier day was fetched before the split.** Everything up to the latest such day is not drawn. The chart
   starts at the first day after it, so there is one share count and never a hole in the middle. Note `split`, which
   names the days and says they "may be" on the old share count.
3. **A day fetched ON the split day, or with no readable stamp.** It is not proven, so it is not drawn
   (`RUNCHART_SPLIT_SAME_DAY_OK = False`, HIS CALL #7).

Edge cases:

- **The split check did not answer.** Every session is drawn and the note `split_unchecked` is added. No name asks again
  for `RUNCHART_SPLIT_RETRY_SEC`.
- **The newest day failed.** No split read is made (the provider is down). An answer already held for the same
  window is still used, so a split found a minute ago keeps its cut and its note. Only when nothing is held does
  the chart say `split_unchecked` (2026-11-26).
- **A split on the oldest day.** It is outside the window, so there is no cut and no note.

## Half days, holidays, thin names

- **Half day.** From 13:00 ET the bars are tagged after-hours, per `alerts._closes`. The cards keep the loader's tag,
  which still calls 13:00–16:00 regular (HIS CALL #10).
- **Holidays and weekends.** Days are walked with `prev_market_day`, so a holiday or a weekend is never listed and never
  asked of the provider.
- **Thin names.** A drawn day with no bar has no `sessions` entry. The EMAs carry across it unchanged.

## Payload keys

The full contract is §3.4 of the spec.

- **Top-level keys:** `state`, `symbol`, `tf`, `frame_min`, `frames`, `title`, `text`, `notes`, `as_of_text`,
  `as_of_bar_t`, `live`, `refresh_sec`, `hint`, `words`, `ran`, `sessions`, `bars`, `curves`, `vol_avg`, `shade`,
  `view`, `seed`, `dropped`.
- **`bars[i]`:** the `support._frame_bars` keys (`t` is the CLOSE stamp in ET) plus `x`, which is the bar's START as an
  ET wall clock written as UTC seconds.
- **Index-aligned lists:** the `curves` values and the `vol_avg` values line up one-for-one with `bars`.
- **Other states:** `busy` is its own four-key answer. `off` and `bad_symbol` read nothing.
- **Golden fixture:** `frontend/src/lib/__fixtures__/ggRunChart.golden.json` is written by the engine test's recipe:

```bash
cd backend && GGRC_WRITE_GOLDEN=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_gajjala_watch_runchart_2026_11_26.py -k golden
```

## Tests

- **Engine:** `backend/tests/test_gajjala_watch_runchart_2026_11_26.py`. It covers spec items 1-22 plus `cached_at`, with
  negatives throughout.
  - **Inputs:** frames, the calendar, loads, the breaker, clean and session tags.
  - **Drawing:** EMA continuity, `chart_x` across the DST change and the payload shape.
  - **Rules:** empty, the split cases, failed / over budget, the day memo, the built memo, the gate and busy, and
    closed-as-of-the-read.
  - **Extras:** the bar cap, VWAP, off / bad symbols, ran, refresh and the words.
  - **Guards and fixture:** the source guards and the golden.
- **Route:** `backend/tests/test_gajjala_watch_runchart_api_2026_11_26.py`. It checks:
  - the owner gate, including other email, no email, a blank header and the `Depends` object;
  - that `?tf=` reaches the engine and `?sessions=` changes nothing;
  - the fault, busy pass-through, NaN, `to_thread`, the real engine through the route, and the public allow-list.
- **Expected red, not this package's:**
  `tests/test_gajjala_watch_api_2026_11_15.py::test_paths_are_the_constants_and_registered_once` (the route list, which
  the main session widens).

## HIS CALLs

1. How many sessions back (5, one constant).
2. VWAP on this chart (OFF).
3. EMA colours (the house 9 yellow / 21 purple).
4. Where else it opens (only the 📅 strip).
5. Who sees it (the owner).
6. A `TV ↗` link instead.
7. Splits: a day saved on the split day, and re-reading old days.
8. What is on screen when it opens.
9. A live candle (not built).
10. Half-day shading on the cards.
11. EMA warm-up (1 session).
12. Anything else on the chart (not built).
13. The ✨ badge spot.
14. The 👀 Watch's first chart.
15. Any rule from the count (none).
16. Which clock a bar carries (START here, CLOSE on the cards).

Display only. Nothing here rings, gates, sorts or adds a name. UNMEASURED.
