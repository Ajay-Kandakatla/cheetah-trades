# 🗂️ Chart Maps tab membership snapshot (2026-10-12)

Ajay's his-call #8: *"Link each new name to the other Chart Maps tabs it's on?
That needs a stored per-tab snapshot first."* → "yes". This is the stored
snapshot plus the one read that feeds `arrivals[i].also_on` on `/growth/board`
and `/growth/tags`. It changes no board, sort, filter, gate or push.

Code: `backend/chart_maps/membership.py` · hooks in `backend/chart_maps/board.py`
(`board()`, right after `out["tab"] = t`) and `backend/sepa/bonde_api.py`
(`bonde_board._run`) · tests `backend/tests/test_chart_maps_membership.py`.

## Schema — collection `chart_maps_membership`, one doc per tab

| key | meaning |
|---|---|
| `_id`, `tab` | the tab key (`zones`, `ath`, `bonde`, …) |
| `symbols` | the served symbols, upper-cased, de-duplicated, served order |
| `n` | `len(symbols)` |
| `built_at` | when the snapshot was written (UTC ISO) |
| `source_as_of` | the DATA's as-of: a memo tab's own block `built_at` (`out["<tab>_board"]["built_at"]`); else the payload's `built_at` / `as_of` / `generated_at`; Bonde: its `scan_ts` |
| `ttl_sec`, `ttl_name` | the tab's own cache TTL constant, value and NAME (`chart_maps.ath_tab.MEMO_TTL_SEC`); `None` when the tab has none |
| `params_note` | the request the list came from ("default page request: limit=80 days=130 …") |
| `limit` | the served cap (80 on a page load); `None` for Bonde |

Nothing about users: no user, email, holdings or owner key (pinned by a
negative test).

## Writer rule

`board()` upserts ONE doc (`replace_one(..., upsert=True)`) only when ALL hold:

- the request is the **default page request** — `is_default_request(**request)`
  reads every default from `inspect.signature(board.board)` (never a typed
  list) with four overrides: `limit == board.LIMIT_MAX` (the page's
  `BOARD_LIMIT`, not the Python default `LIMIT_DEFAULT`), `days ==
  board.BARS_DEFAULT`, `studies is False`, `min_room is None or ==
  supply_demand.room_floor.MIN_ROOM_DEFAULT` (the page sends 5 explicitly on
  zones / deep_demand / quick_bounce / breaking and `board()` treats None and
  5.0 identically). Every other argument must equal its signature default.
  An argument `board()` does not have → one warning + no write (never a
  TypeError); a signature parameter missing from the hook → no write. A CI pin
  checks the hook passes exactly the signature's parameter set;
- the payload is not `warming`;
- the tile list is non-empty — an error / no-scan / warming block never
  overwrites the last real list (the as-of stays at the last non-empty build);
- the tab is not `supply` (hidden alias of ict) or `growth` (itself).

So `?room=any` (`min_room=0`), a non-default sort / tier / phase / filter, the
`uv=peers` view, studies on, or a smaller limit never write. A direct
in-container call of the API handler hands it Query objects, its coercion
falls back to non-default values, and it never writes either.

Other writers:

- **`supply_demand.session_board.board_symbols()`** calls
  `board(tab, limit=LIMIT_MAX, universe="full")` for zones and deep_demand on
  its own (cron / session) cadence — a default request with `min_room=None`,
  so it **writes** and refreshes those two as-ofs. Same list, never a
  different one.
- **Bonde** (`GET /bonde/board`): `record_bonde` walks `sepa.bonde.SECTIONS`
  in order, first placement wins, `rejected` never walked (the
  `board_arrival.bonde_rows` walk without its ✨ new cut). No TTL constant →
  staleness not judged.

Every writer swallows its own errors (logs, returns False): a Mongo failure
never breaks a board (pinned: `board()` with the hook raising and with Mongo
raising both return the board).

## Membership = the served top `limit`

A tab's doc holds what that tab SERVED — the top 80 on a page load — not every
name the tab's screen matched. A name ranked 81st reads as absent. Every
surface that shows `also_on` says "in the served top {limit}" (the field rides
on each `also_on` entry).

## Reader and staleness

`attach_also_on(arrivals)` makes ONE projected `find({})` over at most 23 tiny
docs, then sets `a["also_on"] = [{tab, built_at, source_as_of, ttl_name, limit,
stale}]` per arrival, tabs sorted by key, `growth` excluded. Empty / missing
collection or no Mongo → `[]`; an exception leaves the arrivals untouched.
O(1) reads per arrivals request.

`stale` is judged from `source_as_of` first (the memo block's own build stamp,
which can already be up to one TTL old when served — stale-while-revalidate),
`built_at` only as the fallback, against that tab's own constant:

| tab | constant |
|---|---|
| key_levels | `chart_maps.key_levels_tab.MEMO_TTL_SEC` |
| ath | `chart_maps.ath_tab.MEMO_TTL_SEC` |
| fallen | `chart_maps.fallen_tab.MEMO_TTL_SEC` |
| dual_momentum | `chart_maps.dual_momentum_tab.MEMO_TTL_SEC` |
| resiliency | `chart_maps.resiliency_tab.MEMO_TTL_SEC` |
| drop10 | `chart_maps.drop10_tab.ttl_for(mode)` → `LIVE_TTL_SEC` / `CLOSED_TTL_SEC`, `mode` read from `out["drop10_board"]["mode"]` |
| every other tab, Bonde | none → `stale: null`, as-of shown, not judged |

No new threshold anywhere; a naive stamp is read as UTC; an unparseable stamp
→ `stale: null`.

## Coverage

Covered (≤ 23 docs): the 22 `board.TABS` minus `supply` (alias) — vcp,
topping, zones, ict, deep_demand, quick_bounce, breaking, gabbar, undervalue
(💎 default view only), zero_dte, winners, earnings, keltner, amd, ipo,
key_levels, dual_momentum, ath, resiliency, fallen, drop10 — plus `bonde`.

| NOT covered | why |
|---|---|
| holdings, signals, ema_frames | per-USER lists — never snapshotted into a shared collection |
| support | per-ticker tool, no list |
| news | headlines, no symbol list |
| hot_sectors | sector rows |
| growth | the arrivals board itself |
| session, overnight, catalysts, hot_pullback, patterns, gnt, potus | own endpoints outside `board()` — HIS CALL to extend |
| supply | hidden alias of ict |

## Cost

Read (measured 2026-10-12 10:13 CT, api container, read-only, 20 runs, median /
max): projected `find({})` over `growth_seen` (41 tiny docs, the same shape
class) **0.25 ms / 0.46 ms**; `find_one` over `growth_board` **0.27 ms /
0.41 ms**; the projected find over `chart_maps_membership` (absent before
deploy) 0.12 ms / 0.54 ms. The added read is sub-millisecond.

Write: NOT measured pre-deploy (probes never write to Mongo). After deploy the
main session reads the debug line `membership: wrote <tab> n=<n> in <X> ms` on
the first default page load and records X here: _pending_.

`/growth/tags` wall time before / after (curl `-w %{time_total}`, 5 runs each,
also measures the `to_thread` move): _pending, post-deploy_.

## What it is not

Not a signal and not measured as one: a name being on another tab's list says
nothing about its forward return. Nothing sorts, hides, gates or pushes on it
(Rule #10 source pin: `membership.py` contains no tile sort, no push, no alert
gate, no typed TTL number).
