# 🚩 Gajjala's 1-minute page (2026-10-27)

Spec: BUILD_SPEC27. Tab `gajjala_1m` on Chart Maps, right after 🚩 Gajjala's. **UNMEASURED.** Nothing has measured a
1-minute read. The 2026-10-14 study of the 5-minute setups read NULL (docs/gajjala/study_2026_10_13.md). This page makes no
edge claim, and its 🏁 Track record is operational accounting, not a backtest.

## The ask, verbatim

Ajay, 2026-10-27, about 11:35 ET:

> "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles please."

> "do everything and also add the track record for it from today.."

## 2026-10-29 — LIVE (HIS CALL #1 answered)

Ajay, 2026-10-29, about 12:30 ET:

> "Only give me Gajjalas chart notifications from both tabs,
>
> I am missing out the ones in noise."

"Both tabs" = 🚩 Gajjala's and this page. So, since 2026-10-29:

- `GAJJALA_1M_PUSH_MODE = "live"` (its comment starts `Ajay 2026-10-29` and carries his words, pinned by
  `tests/test_gajjala_constants.py::test_the_1m_push_mode_line_is_tagged_his`). An A+ calls
  `push.hooks.notify_gajjala_1m_setup` once per name, setup and day; a first-sighting 🧠 potential calls
  `notify_gajjala_1m_potential` once per name, setup and session. Same gates, same windows, same claims as before.
- Both kinds joined the owner keep-set (`push/subs.OWNER_KEEP_SET`, now six kinds: see
  `docs/notifications/owner_keepset_2026_09_20.md`, section 2026-10-29). `default_prefs()` still has both False for
  everyone else.
- **History stays honest.** 2026-10-27 to 2026-10-28 every 1-minute alert was recorded in shadow, never sent. Those rows
  keep their shadow state. On the 🏁 Track record a 🧠 row's kind word is read from its OWN push state: "🧠 shadow —
  never sent" for a shadow row, "🧠 live" for a pushed one, a neutral "🧠 potential (1-minute)" if it carries neither. The
  A+ rows read their line, which is the claim's own state ("A+ shadow — never sent" / "🎯 A+ entry"). The counts lead
  says shadow, live or both, from the rows of the span.
- **The words follow the mode.** `variant.WORDS_1M` carries the live sentences (they name the shadow period and his
  words). If the constant is ever flipped back, `variant.word()` serves the 2026-10-27 shadow sentences
  (`WORDS_1M_SHADOW`) instead, so the page never says "rings your phone" while nothing rings.
- **The shadow-key guard stays.** A live claim checks for its `SHADOW:GG1:` twin first. An A+ the shadow already recorded
  that day never rings after the flip: no double record, no late ring. Pinned by
  `tests/test_gajjala_only_pushes_2026_10_29.py::test_NEGATIVE_the_shadow_key_guard_refuses_the_live_claim`.
- Not changed: every gate, window, threshold and the cron. The 🚩 Auto-Pilot lane still reads GG5 claims only.
- The ℹ️ Rules panel clause (`backend/supply_demand/rules_info.py` `_gg_one_minute_clause`, a words-only edit, no gate)
  follows the mode too: live, it says the alerts ring your phone since `variant.LIVE_SINCE_1M` and that the days from
  `GG1M_RECORD_FROM` until then were recorded in shadow, never sent. Shadow, it says "its alerts are recorded in shadow,
  never sent." Pinned both ways by `tests/test_gajjala_1m_page_2026_10_27.py`.
- Deploy order: `api`, then `scripts.owner_prefs_apply` (dry, then `--apply`), then `cron frontend`. If the cron goes
  live first, an alert is claimed while his devices still read the 1-minute kinds as off, and it is lost for the day.
  The runbook is in `docs/notifications/owner_keepset_2026_09_20.md`.

## What it is

The page runs the whole 🚩 pipeline on CLOSED 1-minute bars: GG's five setups, K1–K11, the A+ claim, the 🧠 potentials, the
📈 track, and the 🏁 Track record with the 🎯 A+ filter and charts. The ➖ Fade reads 5-minute bars first, the same way the
5-minute page reads 15-minute bars first. The page uses the same scanner list as 🚩 Gajjala's and reads about once a
minute. **2026-10-27 to 2026-10-28 every alert on this page was recorded in shadow and never sent; since 2026-10-29 they
are live** (see above). The 🏁 record starts 2026-10-27 (`GG1M_RECORD_FROM`), with no replay and no backfill.

GG trades these setups on 5-minute bars, so this page is a Cheetah variant. His rules are counted in bars, and each one
now counts 1-minute bars (HIS CALL #5).

## One pipeline, two variants

`backend/chart_maps/gajjala/variant.py` holds a frozen `Variant`. There is one engine per concept: the detectors, alerts,
potentials, ledger, tape and board are shared, and each takes a variant.

| | GG5 — 🚩 Gajjala's | GG1 — 🚩 Gajjala's 1-min |
|---|---|---|
| key / tab | `gajjala` | `gajjala_1m` |
| label | Gajjala's | `GG1M_TAB_LABEL` = "Gajjala's 1-min" |
| frames (primary, slow) | 5m, 15m | 1m, 5m |
| cadence | `PASS_CADENCE_SEC` (the 🚩 cron line) | `GG1M_CADENCE_SEC` = 60 (the spawned loop) |
| collections | `gajjala_*` | its own `gajjala_1m_*`; shared ones read from GG5 |
| claim prefix | `GG:` | `GG1:` (shadow `SHADOW:GG1:`) |
| push kinds | `gajjala_setup`, `gajjala_potential` | `gajjala_1m_setup`, `gajjala_1m_potential` |
| push mode | `GAJJALA_PUSH_MODE` (live) | `GAJJALA_1M_PUSH_MODE` = "live" since 2026-10-29 ("shadow" 2026-10-27 to 10-28) |
| api base | `/chart-maps/gajjala` | `/chart-maps/gajjala-1m` |
| entry tape | `LEDGER_TAPE_TF_MIN` | `GG1M_TAPE_TF_MIN` = 1 (up to `GG1M_TAPE_BARS_MAX` = 2,880 bars) |
| stale after | `STALE_AFTER_SEC` | `GG1M_STALE_AFTER_SEC` = 300 |
| 🚩 Auto-Pilot lane | consumes its claims | never (HIS CALL #9) |
| 🏁 headline counts | potentials pushed | potentials pushed or shadow |

**GG5 does not move.** Every byte it stores or serves is unchanged. That is proven by
`tests/test_gajjala_variant_gg5_identity.py`, which compares every write and all 10 boards against fixtures captured on
the untouched tree, and by the three goldens (on_open, potential_tab, track_record_tab).

### Collections

- **GG1's own collections** (`store.OWN`, written by GG1 only): `gajjala_1m_passes`, `gajjala_1m_reads`,
  `gajjala_1m_alerts`, `gajjala_1m_state`, `gajjala_1m_potentials`, `gajjala_1m_ledger`, `gajjala_1m_replay`.
- **Shared with GG5** (`store.SHARED`, read-only for GG1): `gajjala_scan`, `gajjala_ah_carry`, `gajjala_post`,
  `gajjala_halts`, `gajjala_daily`. The broker list is still the ONE `gajjala_state` doc.
- GG1 never scans. Its names come from GG5's listed names, capped at `GG1M_MAX_NAMES` = 60 and ordered by today's
  change. Each name's ctx (float, halts, psych) is GG5's stored ctx, so it can be up to one 5-minute pass old. The strip
  and the ☀️ / 🌙 subs are GG5's, copied verbatim with `from_pass`.

## Cadence: how the loop runs

1. At the end of each 5-minute cron pass, `run.main` spawns a detached `python -m chart_maps.gajjala.run_1m --loop`
   through `run._spawn_1m` → `run_1m.spawn_loop` (`start_new_session`, `close_fds`). It then returns at once. It does
   this only on the cron path: `--dry-run`, `--now`, `--on-demand` and `--symbols` never spawn, and a failed spawn never
   changes the exit code.
2. The loop reads one closed 1-minute bar per iteration. Iteration 0 runs right after GG5's pass; later iterations run at
   :30 of each following minute, so a slot has at most 5 iterations. An iteration starts only when
   `start + GG1M_MINUTE_BUDGET_SEC (35) + GG1M_SLOT_MARGIN_SEC (20) ≤ the next cron tick`. The loop stops at the
   session's extended close.
3. A GG1 lease (`GG1M_LEASE_SEC` = 55 s, gap `GG1M_LEASE_MIN_GAP_SEC` = 0) serialises iterations. It is separate from
   GG5's lease, so a held GG5 lease never blocks GG1. A second cron loop is refused.
4. When the loop ends it writes a `gajjala_1m_state` doc `loop` with the reason: "no time left in the slot", "after the
   extended close", "off" or "lease held".

**The supercronic trap.** Supercronic runs without `-overlapping`. If a job is still running at the next tick,
supercronic SKIPS that tick, and that tick is the live 🚩 pass. That is why the loop is a detached child and never runs
in-process. **Never move the loop back inside `run.main`.** The contract "🚩 Gajjala 1-minute page (2026-10-27)" fails if
`run.py` calls the loop directly. tini is PID 1, so it reaps the detached child.

**No crontab line.** A deploy never ships the host-mounted crontab, so this page needs no crontab edit. The contract also
fails if `backend/crontab` names `run_1m`.

**Kill switch.** Set `GAJJALA_1M_ENABLED = False` (needs a cron deploy), or set the env `GAJJALA_1M_ENABLED=0` in the cron
container's environment (needs a recreate). Either one stops the spawn and every iteration.

## Costs

- **Massive minute fetches (the one new cost, HIS CALL #11).** Up to 60 forced fetches per iteration and up to 5
  iterations per 5 minutes, so up to about 60 calls a minute: roughly 4–5× GG5's minute-bar load.
- **Mongo.** Up to 60 read docs are replaced per iteration (about 25–40 KB each with the 192-bar tile cap), so up to
  about 2 MB a minute. `gajjala_1m_passes` holds about 960 docs per session under the 30-day TTL.
- **Coverage (HIS CALL #13).** When GG5's pass runs past about 30 s, the bar that closes at the tick is read late. That
  minute's A+ is "late" and is not recorded as A+.
- **Ambiguous entries.** A 1-minute entry bar holds ONE minute. If that minute crossed both the trigger and the stop, the
  read is always "ambiguous" (his rule 10 as written). Expect more "broke — not A+" than on the 5-minute page.

## Served surface

- `GET /chart-maps/gajjala-1m` takes the same params as the 5-minute GET and serves the extra `variant` block: title,
  honesty, tfs `["1m", "5m"]`, `record_from`. All of its words come from `variant.WORDS_1M`.
- `POST /chart-maps/gajjala-1m/scan` is the owner's on-open pass. Non-owners get a stealth 404, as on the 5-minute page.
- `GET /chart-maps/gajjala-1m/entry-tape` serves the 🏁 entry tape on 1-minute bars. Its memo is keyed per variant.
- The broker-flag routes stay ONE list under `/chart-maps/gajjala/…`.
- The frontend types none of these words. `GajjalaBoard` takes `variant="gajjala_1m"` and is mounted with
  `key="gajjala_1m"`. Without the key, React would reuse the 🚩 board: it would keep that board's state and skip the
  on-open POST.
- The /alerts page and the notification settings carry both kinds. They were labelled "(shadow)" until 2026-10-29; the
  labels now read "Gajjala 1-min A+" and "Gajjala 1-min potential". Both kinds default to off for everyone else and are
  ON for the owner through the six-kind keep-set.

## HIS CALL (defaults shipped; none decided for him)

1. ~~GG1 push mode is SHADOW for both kinds (`GAJJALA_1M_PUSH_MODE`). Going live means changing that constant and
   adding the two kinds to OWNER_KEEP_SET.~~ **ANSWERED 2026-10-29: "Only give me Gajjalas chart notifications from both
   tabs"** — the constant is "live" and both kinds are in the keep-set. Going back is one word (the constant).
2. The 🏁 headline % pools the 🧠 potentials recorded in shadow (never sent). The alternative is to count nothing until a
   kind is live.
3. Names are GG5's listed names only, capped at 60 by today's change (`GG1M_MAX_NAMES`). The alternatives are every listed
   name, or a scan of the page's own.
4. K11 reads today's 1-minute volume summed through the latest closed bar. The 1M floor is the same as GG5's; the source
   is different (GG5 reads the snapshot volume).
5. The bar-count K-rules count 1-minute bars: the K1 20-bar range is 20 minutes, K4's 1–5 bar pullback is 1–5 minutes, and
   the 9/21 EMAs run on 1-minute closes. His first-15-minutes rule stays on the wall clock.
6. The ➖ Fade reads 5-minute bars first, then 1-minute (the 15→5 analog). The alternative is 1-minute only.
7. A 1-minute card draws the last 192 bars (`GG1M_TILE_BARS_MAX`).
8. The 🏁 entry tape draws 1-minute bars (up to 2,880). The alternative is the 5-minute tape.
9. The 🚩 Auto-Pilot lane consumes GG5 claims only. GG1 never trades.
10. The tab sits right after 🚩, labelled "Gajjala's 1-min".
11. The new cost: up to 60 Massive minute fetches per iteration, about 60 calls a minute. The options are fewer names, or
    a pass every 2 minutes.
12. /alerts gains two rows that never rang while the kinds were shadow (since 2026-10-29 they count `pushed`). Keep them
    or drop them. 2026-10-27 (critic
    findings 1 and 2): the rows sit in their own strip (`GG1M_PASSES`, after the tape strips), outside the intraday
    "all 7 passes" header, so a switched-off 1-minute page never turns that header into a warning.
13. Coverage: when GG5's pass runs past about 30 s, the minute that closes at the tick is read late.
14. There is no ⌘K entry for the 1-minute page (the ask was scoped to the board).
15. The track record runs from 2026-10-27 only, with no replay and no backfill.

## Verification recipe

Hermetic backend tests (network none):

```bash
/usr/bin/find /Users/ajay/clinet-test/wt-gg1m/backend -name __pycache__ -type d -prune -exec rm -rf {} +
docker run --rm --network none --name cheetah-tmp-pytest-gg1e -v /Users/ajay/clinet-test/wt-gg1m:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_variant_2026_10_27.py tests/test_gajjala_variant_gg5_identity.py tests/test_gajjala_run_1m_2026_10_27.py tests/test_gajjala_1m_page_2026_10_27.py
```

Frontend:

```bash
cd /Users/ajay/clinet-test/wt-gg1m/frontend
rtk proxy npx vitest run src/components/GajjalaBoard.variant.test.tsx src/lib/chartMaps.test.ts src/lib/momentumBurst.test.ts --reporter=dot
rtk proxy npx tsc --noEmit -p .
rtk proxy node scripts/contracts.mjs
```

Throwaway dry run before the deploy: one iteration of up to 60 fetches, run outside the api. Its `writes` must name only
`gajjala_1m_*` collections, and `sent` must be empty.

```bash
docker run --rm --name cheetah-tmp-gg1m-dry --network cheetah-market-app_default --env-file /Users/ajay/clinet-test/cheetah-market-app/backend/.env -v /Users/ajay/clinet-test/wt-gg1m:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m chart_maps.gajjala.run_1m --dry-run --json
```

After `./deploy-cheetah-main.sh api cron` (frontend tonight). Deploy between ticks (:x2–:x4): restarting supercronic can
lose the 🚩 tick at the restart minute.

1. Watch the cron log for 15 minutes. Every :x1 / :x6 🚩 pass line must still be there, with no supercronic "skipping"
   line, and there should be one "gajjala 1m loop" spawn line per slot.
2. Run a read-only probe of the api container: the age of `gajjala_passes` "latest_cron" is under 300 s;
   `gajjala_1m_passes` has about 5 docs per slot with `wall_s` and `bars.over_budget`; every `gajjala_1m_alerts` id
   starts `SHADOW:GG1:`; there is no push receipt for either 1-minute kind. (That was the 2026-10-27 shadow check. Since
   2026-10-29 a rung A+ is a `GG1:` id in state `pushed`, and both kinds leave push receipts.)

```bash
docker exec -i -w /app cheetah-market-app-api-1 python - <<'EOF'
from chart_maps.gajjala import store as ST, variant as V
st = ST.for_variant(V.GG1)
print(st.physical(ST.PASSES), st.physical(ST.ALERTS))
EOF
```

3. Send ONE GET each with `X-User-Email: ajaykandakatla@gmail.com` to 127.0.0.1:8000:
   `/chart-maps/gajjala-1m?sub=potential`, `/chart-maps/gajjala-1m?sub=track_record&span=today`, and
   `/chart-maps/gajjala?sub=potential`. The last one's key set must equal a GET taken before the deploy.

```bash
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8000/chart-maps/gajjala-1m?sub=potential"
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" "http://127.0.0.1:8000/chart-maps/gajjala-1m?sub=track_record&span=today"
```

4. Tomorrow morning, `?sub=track_record&span=yesterday` on the 1-minute page should show tonight's 20:15 grades. Tonight,
   after the frontend deploy, open https://pounce.ajaykandakatla.dev/chart-maps?tab=gajjala_1m at 430 px.
