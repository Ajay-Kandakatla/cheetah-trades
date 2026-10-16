# 🔄 Gajjala's tab — scan on open + 🎯 A+ banner (2026-10-15)

**UNMEASURED — not a recommendation.** The study of his A+ setups read no edge (`docs/gajjala/study_2026_10_13.md`,
MEASURED 2026-10-14, NULL); nothing on the banner claims one.

Ask dated 2026-10-15; the deploy and the live proof are dated 2026-10-16 (AMENDMENTS5 A16).

## The ask (verbatim)

> "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any enterable stocks on
> the top which I see in potential i guess"

He acts on what the banner shows (real money). His knob answers (AskUserQuestion 2026-10-15 ~16:2x ET, DECISIONS5):

- **K1 "Enterable" = A+ only** — the card state `aplus`: every rule of the setup met, price traded THROUGH the trigger
  and the entry bar CLOSED (GG: "right at the break"). Not `triggered` (the entry printed earlier), not `forming` /
  armed potentials, not `partial`. The banner lists the A+ reads of the LATEST pass only.
- **K2 Refresh the read only** — an open rings no device. On an on-open pass BOTH push gates run dry
  (`alerts.run_pass(dry=True)`, `potential.run_pass(dry=True)`): no send, no claim, no tracker write, no
  `gajjala_alerts` shadow row, no /alerts row. Pushes stay on the 5-minute cron pass.
- **K3 🎯 line on every sub, first in 🧠 Potential** — one line right under the sub-tab row (symbols with deep links,
  trigger · stop, "A+ since HH:MM ET"); on 🧠 Potential it sits above the 📈 Track.
- **K4 Every open; reuse a pass under 60 s old** — `ON_DEMAND_REUSE_SEC = 60  # Ajay 2026-10-15`. A pass in flight
  (cron or on-open) is waited for, never doubled. The board on screen stays under a "scanning…" line — never blank.

## How it runs

```
GajjalaBoard mount (owner only, is_admin === true)
  → POST /chart-maps/gajjala/scan                  chart_maps/api.py — owner-only (auth.is_admin_email), else 404
    → on_demand.request()                          Mongo reads only, answers at once
       closed | waiting | reused | started | refused
    → on "started": subprocess.Popen(python -m chart_maps.gajjala.run --on-demand, start_new_session=True)
         → run.run_on_demand → run_pass(on_demand=True): ON_DEMAND_BUDGET_SEC bar budget, no Yahoo float
           refinement, BOTH push gates dry, own pass doc "{date}|{HH:MM:SS}|open" (on_demand: true)
  → the board re-reads the existing GET /chart-maps/gajjala until pass.at moves (or the served wait max runs out)
```

The on-open pass is a **subprocess, never a thread in the api** (AMENDMENTS5 A1): the pass is CPU-heavy pure Python and a
thread would hold the single uvicorn worker's GIL for the whole pass — the 2026-09-30 HTTP 524 class of failure. The api
process never imports or calls `run_pass` / `run_on_demand`; it reads the pass doc and the lease, and spawns. The
child's stdout / stderr are inherited, so its one line (`gajjala on-open pass: {...}`) lands in the api's docker log.

`request()` order (every step soft, never raises):

1. **closed** — a closed day (`market_hours.gate.closed_reason`) or outside the pass window (`run.in_window`,
   04:00–20:05 ET): no child, no lease read (C6).
2. **waiting** — this process's child is still alive (two opens within a second → one child).
3. **waiting** — the pass lease is held (a cron or an on-open pass is in flight — K4).
4. **waiting** — the session's first 5-minute pass has not landed yet (A12): no spawn; the 04:01 tick does the type map.
   2026-10-16 (final critic): this gate reads the `latest_cron` pointer ONLY, never the `latest` fallback the banner
   keeps (`tab._cron_ref`). Only a cron of this image writes that pointer, and only a cron of this image waits for an
   open's lease; a cron left on the old image reads an open's `status: running` lease as held and skips its tick (its
   A+ and LIVE 🧠 pushes with it). No pointer → `waiting`, no spawn — and the deploy is `api frontend cron` together.
5. **reused** — the latest pass finished under `ON_DEMAND_REUSE_SEC` ago (`finished_at`, else `at + wall_s`), or a
   scan on open released the lease under that long ago (`lease_state` `held_by on_demand` + `status done` + `done_at`):
   an open that re-read nothing leaves `latest` alone (A13) yet still counts, else every open re-spawned and the board
   said "scanning…" for 90 s (final critic 2026-10-16). W11b: "🔄 a scan on open finished N s ago — reused (…)".
6. **started** — the child is spawned; a spawn that raises → **refused**.

Every POST answer carries exactly `state, latest_at, eta_sec, poll_sec, wait_max_sec, text`. `latest_at` is
`tab.pass_stamp(latest)` — the SAME function that serves the GET's `pass.at`, so the board knows the awaited pass has
landed by string inequality. started / waiting carry the poll plan; reused / closed / refused carry none.

### The board's loop (GajjalaBoard.tsx)

- ONE POST per mount, owner only (the server lock is the second guard; StrictMode's double effect keeps the ref).
  Sub-tab clicks do not remount, so they never POST again; leaving the tab and coming back does.
- started / waiting → a chain of `setTimeout`s on the SERVED plan (never a second `setInterval`): the first re-read after
  `eta_sec`, then every `poll_sec`, giving up at `wait_max_sec`. Each step is a re-read of the existing GET.
- The poll stops when the served `pass.at` differs from the POST's `latest_at` and `scan.state` is not `scanning`.
- reused for a pass newer than the one on screen → exactly one re-read; reused for the same pass, closed → no extra GET.
- refused → the served refused line, no poll. A non-owner 404 or a network error → nothing shown, no poll.
- Non-owners (household users) never POST and see no 🔄 button and no scanning line; the 🎯 line and the as-of line
  still render from the GET (the cron read).

## The split lease (store.py, run.py) — the cron cadence is sacred (C1)

| Lease doc state | cron tick | on-open claim | POST answers |
|---|---|---|---|
| free, last cron start ≥ 240 s ago | claims (`claimed`) | claims | started (unless reused) |
| free, last cron start < 240 s ago | refused `gap` (the unchanged duplicate-cron guard) | claims (no gap — C1) | started (unless reused) |
| held by cron (fresh) | refused `held` (unchanged) | refused `held` | waiting |
| held by on_demand (fresh) | waits ≤ 45 s (9 × 5 s), then `taken_over` | refused `held` | waiting |
| held, claimed ≥ `LEASE_SEC` ago (crashed holder) | claims | claims | started |
| legacy medical-shape doc (no `held_by`) | gap vs its `started_at` | claims when not running | as above |
| not in window / closed day | `run.in_window` exits before the lease | same | closed (no lease read, no child) |

- The min gap compares against the last **cron** start only (`last_cron_started_at`), and that stamp is the tick's own
  clock — the `now` the tick was called with, before any wait (A6).
- An on-open claim needs only "not held" and writes `od_started_at` + `held_by`, never `started_at` (A9: the old image's
  `claim_lease` gaps against `started_at`, so it cannot see an open).
- A cron tick that finds an on-open pass holding the lease WAITS (polling every `ON_DEMAND_POLL_SEC`) at most
  `CRON_WAIT_ON_DEMAND_SEC`, then takes the lease over (`taken_over`) — it never answers refused because of an open. A
  release seen between the claim and the classify read is retried on the next poll (A7).
- Releases are token-guarded. A superseded on-open pass checks `store.lease_owner_is(token)` before every write of its
  tail; after a take-over it stops writing (`status "superseded"`, exit 0) — the cron's reads survive byte-equal (A8).
  2026-10-16: the same check runs in `_finish` before the pass doc, so a body that raises an ordinary error after a
  take-over writes no `|open` error doc either.
- Every stamp read back from Mongo goes through `store._utc()` first: the live client is not tz-aware and hands back
  NAIVE UTC (A5).

### The C1 arithmetic (constants.py; pinned by the WP-A tests and the contracts block)

```
CRON_WAIT_ON_DEMAND_SEC + LEASE_MIN_GAP_SEC < PASS_CADENCE_SEC      45 + 240 = 285 < 300
ON_DEMAND_BUDGET_SEC < PASS_BUDGET_SEC                              45 < 240
CRON_WAIT_ON_DEMAND_SEC <= ON_DEMAND_BUDGET_SEC                     45 <= 45 (derived: equal)
CRON_WAIT_ON_DEMAND_SEC % ON_DEMAND_POLL_SEC == 0                   45 / 5 = 9 polls exactly
ON_DEMAND_WAIT_MAX_SEC = 2 × ON_DEMAND_BUDGET_SEC                   90 s — the board stops waiting after it
```

Measured 2026-10-15 from the live pass docs (read-only), cited in the constants comment: pass wall time p50 5.6 s, p90
11.7 s, p99 18.2 s, max 34.7 s (16:06 ET, 66 names); cron start offset after the tick minute (424 pass docs) p50 0.8 s,
7 starts ≥ 10 s, max 58.5 s. Because the gap clock is the tick clock (A6), a tick 58.5 s late that waits the full 45 s
still leaves the on-time next tick 241.5 s ≥ 240 s after it. Tags: `ON_DEMAND_REUSE_SEC` is his (`# Ajay 2026-10-15`);
the budget, the wait, the poll and the wait max are MINE (`TRANSPORT — MINE` / `derived — MINE`, HIS CALL Q4). Nothing
lists, reads or pushes on these numbers — pacing only.

## Pass-doc hygiene (C5, A10, A13)

- The on-open pass doc id is `"{date}|{HH:MM:SS}|open"` with `on_demand: true` — it never overwrites the cron's minute
  doc `"{date}|{HH:MM}"`.
- Two pointers: `latest` (any pass — the tab's `pass` block and "scanned on open") and `latest_cron` (cron passes only).
  `latest` never moves backwards in time, and does not move when an on-open pass re-read no name (A13). `pass.stale` and
  the 🎯 gate read `latest_cron`, so opens alone never hide a dead cron (A10). /alerts `alert_pass_latest` stays the
  cron's.
- Closed bars only (C3): a pass reads closed 5-minute bars (right label ≥ 30 s old). An open at 14:18 sees the same bars
  as the 14:16 cron pass; what it adds is the fresh whole-market snapshot (new scanner names, live prices). The copy says
  "bars through HH:MM", never a newer bar.

### The D9 continuity argument (§1.2) and its two tests

`potential.run_pass(dry=True)` still sets `counts["tracked_today"] = store.count_potentials(session)` (the real,
cron-written count), so a dry block is a complete count for `_gate_block_ok`. `_previous_pass_ran_gate` reads
`store.recent_passes(session, now − (PASS_CADENCE_SEC + LEASE_SEC), now)` and accepts any earlier pass doc whose block
passes `_gate_block_ok` (`tracked_today` present, and not `joined > 0 and tracked_today == 0`). An on-open pass doc with
a dry block therefore counts as "the gate ran" exactly like a cron pass — and an on-open join never unlocks the next
cron. Pinned by:

- `test_C5_a_quiet_mornings_first_sighting_still_rings_on_the_next_cron_after_an_on_open_pass` — a quiet cron, an
  on-open pass that sees a forming flag (dry, no send, no tracker doc), then the next cron rings it with
  `first_seen_mode "normal"`.
- `test_C5_NEGATIVE_an_on_open_join_never_unlocks_the_next_cron` — no prior pass, an on-open join, then the cron joins
  too and sends nothing.

A potential first seen by an open shows in the 🧠 strip at once WITHOUT "first seen" (the tracker is cron-only); its 📈
Track row and its push start at the next cron pass (K2).

## The two GET blocks (tab.py; every string composed server-side — the board prints what it is given)

### `scan` (every sub, incl. 📓 / ☀️ / 🌙 / 🧠)

`{state: scanning | idle | closed, on_demand, started_at_et, bars_through_et, as_of_text, scanning_text, text, note,
rescan_label, rescan_title}`. `closed` outside the pass window; `scanning` while the lease is held (a lease claimed
`LEASE_SEC` ago is not held — a crashed holder never shows "scanning" forever); else `idle`.

| # | Where | Text |
|---|---|---|
| W1 | as_of, latest on-open, this session | `🔄 scanned on open {HH:MM} ET` + ` · bars through {HH:MM}` |
| W2 | as_of, latest cron, this session | `last pass {HH:MM} ET` + ` · bars through {HH:MM}` |
| W2b | as_of, in window, nothing this session | `last pass {date} {HH:MM} ET — none yet this session` / `no pass on file yet` |
| W3 | as_of, closed | `market closed — last pass {HH:MM} ET {date}` / `market closed — no pass on file` |
| W4 | scanning, held by an open | `scanning… a pass started on open at {HH:MM:SS} ET — the board below is the {HH:MM} ET read until it lands` (no prior: `… — the board fills when it lands`) |
| W5 | scanning, held by the cron | `scanning… the 5-minute pass started at {HH:MM:SS} ET — the board below is the {HH:MM} ET read until it lands` |
| W6 | note (A13), whenever `n_read < n_listed` | `{n_listed − n_read} of {n_listed} names kept their last pass read` |
| W7 | tile chip `read_at` | `read at the {HH:MM} ET pass` (a card whose read is older than the pass shown) |
| W8 | rescan_label | `🔄 scan now` |
| W9 | rescan_title (A13) | `Run one pass now — both push gates run dry, so this pass rings no device; the last pass is reused when it finished under 60 s ago` |

### POST answers

| # | State | Text |
|---|---|---|
| W10 | started | `🔄 scanning on open — started {HH:MM:SS} ET; the board below stays until it lands` |
| W11 | reused | `🔄 the {HH:MM} ET pass finished {s} s ago — reused (a pass under 60 s old is not re-run)` |
| W12 | waiting | open: `🔄 a pass started on open at {HH:MM:SS} ET is still running — showing it when it lands`; cron: `🔄 the 5-minute pass started at {HH:MM:SS} ET is still running — showing it when it lands` |
| W12c | waiting, no cron pass this session (A12) | `🔄 the first 5-minute pass of the session runs at 04:01 ET — showing it when it lands` / `🔄 no 5-minute pass has landed this session yet — the next runs at {HH:MM} ET; showing it when it lands` |
| W13 | closed | `market closed — no scan on open; last pass {HH:MM} ET {date}` / `market closed — no scan on open; no pass on file` |
| W14 | refused | `🔄 the scan could not start (store error) — the board shows the last pass` |

### `enterable` — the 🎯 line (every sub)

`{title, rows: [{symbol, setup, setup_label, frame, trigger, stop, risk_pct, since_et, variant_label, grade_label, href,
text}], empty_text, note}`. Rows (K1 + A11): every listed read OF THE LATEST PASS (its `updated_at` is that pass's clock —
a name the pass did not re-read keeps an older read and is not listed) whose card state is `aplus`, a variant / grade
read included with the card's own words; newest entry bar first, then SETUPS order, then the symbol. Not listed:
`triggered`, `forming` / armed, `partial`, stopped, any read of an older pass. No `alerts.is_fresh` / `pushable`
filter — those are the alert gate's rules, not "A+ on the card" (A11, HIS CALL Q7). Served only inside the pass window
and only while `latest_cron` is within `STALE_AFTER_SEC` (A10). `href` = `/chart-maps?tab=gajjala&sub=<setup>&focus=<SYM>`.

| # | Where | Text |
|---|---|---|
| W15 | title | `🎯 A+ — traded through the trigger and the bar closed (GG's entry) · {n} · UNMEASURED` |
| W16 | row text | `{SYM} · {emoji} {label} · trigger {T} · stop {S} (−{r}%) · A+ since {HH:MM} ET` (+ the card's variant / grade words, + ` (15-min bar)`) |
| W17 | empty, in window | `🎯 No A+ right now · scanned on open {HH:MM} ET · UNMEASURED` / `🎯 No A+ right now · last pass {HH:MM} ET · UNMEASURED` |
| W17b | empty, no pass this session | `🎯 No A+ right now · no pass this session yet · UNMEASURED` |
| W17c | empty, the cron is stale (A10) | `🎯 No A+ shown · the 5-minute pass has not run since {HH:MM} ET — no alert can ring without it; the banner waits for it · UNMEASURED` |
| W18 | empty, closed (C6) | `🎯 No A+ · market closed — last pass {HH:MM} ET {date} · UNMEASURED` / `🎯 No A+ · market closed — no pass on file · UNMEASURED` |
| W19 | note | `A+ = every rule of the setup met, price traded through the trigger and the bar closed — GG: “{Q}” (S8 1:40:56–1:41:55). Listed while the latest pass reads the card A+ and the 5-minute pass is current; an entry that printed earlier and a potential still forming are not listed (your K1 answer). Opening the tab rings no device: both alerts stay on the 5-minute pass. Closed bars only — an open between passes adds new scanner names, not a newer bar. UNMEASURED — the study of his A+ setups read no edge (2026-10-14); not a recommendation.` |

`{Q}` is SLICED from the served 📓 Playbook ENTRY item (S8 1:40:56–1:41:55, `tab._entry_quote`) — never retyped. The
banner never uses S&D's enterable machinery: the per-card chip is S&D's, and `ENTERABLE_KIND` stays without gajjala (C8).

### The K1 cite, corrected (§1.7)

DECISIONS5 K1 cites GG S8 "I do not see my setups for very extended periods". That sentence is his X post
1844811275412627921 (2024-10-11; `verified_rules.json:55-57`, the Playbook "decay" quote), and it is about how RARELY
his setups appear — not about late entries. The served copy never uses it as the reason to leave `triggered` out; the
reason served is his own K1 answer.

## Where it is pinned

- Backend (hermetic, D12): `tests/test_gajjala_constants.py`, `tests/test_gajjala_store.py`, `tests/test_gajjala_run.py`
  (C1 / K2 / C2 / C5 / C6 / C7 / A1 / A8 tests), `tests/test_gajjala_on_open.py` (request states, route, scan / aplus
  blocks, the on-open golden).
- Frontend: `src/components/GajjalaBoard.scan.test.tsx`, `src/lib/gajjala.test.ts`; the live capture test
  `GajjalaBoard.scan_live.test.tsx` is written after the 2026-10-16 capture.
- Contracts: `frontend/scripts/contracts.mjs` "🔄 Gajjala scan on open + 🎯 A+ banner (2026-10-15)" — the POST path and
  method, the owner gate, no EventSource, the mounts and the banner's place above the 📈 Track, the banner reads only its
  block, the owner-only route and a GET that never names the trigger, the constants arithmetic, no crontab line for the
  open, `on_demand.py` spawns a new-session subprocess and imports no pass code, the served words, and the ✨ entry (his
  verbatim, the 60 seconds, the 5-minute step, no forecast words). Mutation-checked: every property broken once fails
  the block.
- ✨ entry `chart-maps-gajjala-on-open-2026-10-15`; SPECS.md Gajjala section bullet "🔄 Scan on open · 🎯 A+ banner".

## Verification (§5)

Backend, hermetic (the api image, never the host venv):

```bash
docker run --rm --network none --name cheetah-tmp-pytest-ggopen -v /Users/ajay/clinet-test/wt-highbeta:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_on_open.py tests/test_gajjala_tab.py tests/test_gajjala_potential_tab.py tests/test_gajjala_source_guard.py tests/test_gajjala_store.py tests/test_gajjala_run.py tests/test_gajjala_constants.py tests/test_gajjala_potential.py tests/test_gajjala_alerts.py
```

Frontend:

```bash
cd /Users/ajay/clinet-test/wt-highbeta/frontend
rtk proxy npx vitest run --reporter=dot
rtk proxy npx tsc --noEmit -p tsconfig.json
rtk proxy node scripts/contracts.mjs
```

Branch proof on an ISOLATED database (≥ 04:01 ET 2026-10-16, inside the pass window; the verify DB is seeded read-only
from live first — A14):

```bash
curl -s -H "X-User-Email: kathakoo1991@gmail.com" http://127.0.0.1:8001/auth/me
curl -s -X POST -H "X-User-Email: kathakoo1991@gmail.com" http://127.0.0.1:8001/chart-maps/gajjala/scan
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H "X-User-Email: nobody@example.com" http://127.0.0.1:8001/chart-maps/gajjala/scan
curl -s -H "X-User-Email: kathakoo1991@gmail.com" "http://127.0.0.1:8001/chart-maps/gajjala?sub=potential" | python3 -c 'import json,sys; b=json.load(sys.stdin); print(b["scan"]["state"], b["pass"].get("at"), b["scan"]["as_of_text"], len(b["enterable"]["rows"]))'
curl -s -o /dev/null -w '%{time_total}\n' http://127.0.0.1:8001/health
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'printjson(db.gajjala_state.findOne({_id:"lease"}))'
```

Before the deploy, the api and cron containers must run the same image (A9), and the deploy carries all three:

```bash
docker inspect --format '{{.Image}}' cheetah-market-app-api-1 cheetah-market-app-cron-1
./deploy-cheetah-main.sh api frontend cron
```

Live proof (pass window; one open = the feature's own load):

```bash
docker logs --since 10m cheetah-market-app-api-1 2>&1 | grep "gajjala on-open pass"
docker logs --since 20m cheetah-market-app-cron-1 2>&1 | grep "gajjala pass:"
curl -s -H "X-User-Email: kathakoo1991@gmail.com" http://127.0.0.1:8000/alerts/status | python3 -c 'import json,sys; p=json.load(sys.stdin)["passes"]; print(p["gajjala_setup"]["as_of"], p["gajjala_potential"]["as_of"])'
```

Expected: the api log shows `ran True` with `wall_s`; every cron tick after the open shows `'ran': True` with
`'lease': {'why': 'claimed' | 'taken_over', …}` and no `lease held` line; both /alerts pass rows keep the CRON's stamps.
Live link: https://pounce.ajaykandakatla.dev/chart-maps?tab=gajjala&sub=potential

## HIS CALL (each ships with the default shown)

- **Q1** Who may trigger a scan: house owners (`auth.is_admin_email` / the `/auth/me` `is_admin` flag, co-owners
  included) — DEFAULT; vs the single primary address (`is_primary_admin`); vs any signed-in household user.
- **Q2** `triggered` names (the entry printed earlier this session) on the 🎯 line: out (default, K1) vs in, tagged "late".
- **Q3** The 60 s reuse (Ajay K4) — keep.
- **Q4** The on-open bar budget 45 s, the cron's wait = the same 45 s, re-checks every 5 s, the board gives up after 90 s
  (all MINE; the measured wall distribution above sits beside them).
- **Q5** The 🎯 line on the other Chart Maps tabs: no (default) — Gajjala's tab only.
- **Q6** The 🔄 "scan now" button beside the as-of line: yes (default).
- **Q7** How long an A+ stays on the 🎯 line: while the latest pass reads the card A+ (default, A11 — a 15-min ➖ Fade A+
  stays as long as its read stays A+) vs the A+ alert's own 330 s window vs hiding variant / grade reads.
- **Q7b** An open whose budget ran out before re-reading an A+ name drops it from the 🎯 line while its card still
  shows A+ with the "read at the HH:MM ET pass" chip (A11 literal; rare at the measured wall p99 18.2 s vs the 45 s
  budget). Default: keep — or also list A+ reads from the newest cron pass for names the open did not re-read, marked
  with their read time.
- **Q8** Re-scan when a backgrounded browser tab / the phone app wakes: no (default — only opening or switching into the
  tab) vs yes.
- **Q9** CLOSED — the subprocess is the design (A1); the in-api thread variant is not offered.
- **Q10** The "read at the HH:MM ET pass" chip on any card whose read is older than the latest pass (default on — it
  also marks a name whose bars failed on a cron pass) vs only after an on-open budget overrun.
- **Q11** /alerts shows the cron passes only (default — an open writes no /alerts row) vs a separate "🔄 on open" row.
- **Q12** Where the 🎯 line sits: right under the sub-tab row (default) vs the very top of the tab.
- **Q13** An open's snapshot can list a name that only qualified in that snapshot; it stays listed for the carry sessions
  and the cron's LIVE 🧠 gate can ring on it later (A15). Default: allowed — an open is a real scan.

## Traps

- Naive Mongo datetimes: `alerts.bar_close_et` reads a naive datetime as ET — every stamp goes through
  `store._utc()` / `tab._at_utc()` first.
- A crashed on-open child (api restart mid-pass) leaves the lease `running` until `LEASE_SEC` (280 s): the cron waits
  45 s then takes it over; POSTs answer `waiting` until it goes stale; the board stops waiting after 90 s.
- An on-open pass writes `gajjala_scan` and the 1-minute cache like a cron pass — the scan record includes on-open
  snapshots (truthful; the ☀️ "since" may be an open's time).
- The scratchpad replay script `probe/potential_volume_replay.py` stubs `claim_lease` / `release_lease` with the old
  signatures — widen them to `lambda now, *a, **k: …` before any re-run.
