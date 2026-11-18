# ⏹ 🚩 Gajjala's 1-minute page — RETIRED, reversibly (2026-11-18)

The 1-minute page (variant `GG1`, tab `gajjala_1m`, live since 2026-10-27, ringing his phone since 2026-10-29) is
retired by his call. Its pass stops; its history stays; the 👀 Gajjala's Watch keeps its 1-minute charts. Nothing is
deleted, and turning it back on is one word. **UNMEASURED** — nothing new was measured to make this call.

## His words, verbatim

Ajay, 2026-11-18, about 00:10 ET, after the served 🏁 counts below:

> "This is good info stop 1 min tab it was a good experiment"

Ajay, 2026-11-18, about 00:20 ET:

> "But keep the one min chart in the watch list I still want them"

Earlier the same night:

> "I feel 5. mins kiss and fly are more safer"

## The numbers he was shown (served 🏁 Track record counts, about 00:05 ET)

| page | span | A+ W / L | net R |
|---|---|---|---|
| 🚩 5-min | last 10 sessions | 16 / 12 | +4R |
| 🚩 1-min | last 10 sessions | 17 / 23 | −6R |
| 🚩 1-min | all-time (2026-10-27 →) | 21 / 28 | — |

Small n. **UNMEASURED.** These are the 🏁's operational accounting graded by GG's trade math, not a backtest. W / L
alone never ranks a lane — the R totals ride beside them, and nothing here is a confidence interval or beats a
placebo. The prior on any 1-minute read was already null (the 2026-10-14 study of the 5-minute setups read NULL,
`docs/gajjala/study_2026_10_13.md`).

## How it is done — the ONE existing switch

`backend/chart_maps/gajjala/constants.py`: `GAJJALA_1M_ENABLED = False` (its comment starts "Ajay 2026-11-18" and
carries his sentence), plus `GAJJALA_1M_RETIRED_ON = "2026-11-18"` (served in the retired words only; no gate reads
it). No second switch. `GAJJALA_1M_PUSH_MODE` stays `"live"` — the words follow the switch, not the mode.
`variant.enabled(v)` is the ONE predicate every GG1 entry point reads (always True for 🚩 5-min and 🧪 Audited);
`run_1m.enabled()` returns it. The env `GAJJALA_1M_ENABLED` is not set anywhere in compose or the deploy script, and
none is added — the constant governs api and cron alike.

## WHAT STOPS

- **The spawn.** The 🚩 cron pass no longer spawns the detached `run_1m --loop` child (`run._spawn_1m` logs
  "gajjala 1m loop: off (GAJJALA_1M_ENABLED — the page retired 2026-11-18) — not spawned").
- **The pass.** `run_1m.run_iteration` returns `reason "off"` before the store, the lease or any bar read — for the
  cron, dry and on-demand paths alike.
- **The fetches.** Up to about 60 Massive minute fetches a minute during the pass window — gone.
- **The pushes.** `alerts.run_pass` and `potential.run_pass` on the GG1 store return all-zero counts plus `off: 1`
  before any compose; both `_default_send`s refuse with `variant.RETIRED_NEVER_SENDS`. No `gajjala_1m_setup` 🚩 A+ and
  no `gajjala_1m_potential` 🧠 is composed or sent.
- **The loop's state write.** The off loop returns without writing a `loop` state doc and constructs no store (the doc
  already in `gajjala_1m_state` is history).
- **The on-open 🔄.** `POST /chart-maps/gajjala-1m/scan` is refused FIRST, in every window (closed days included), with
  the served sentence "🔄 not run — this page retired 2026-11-18 by your call …" — never "market closed", no child.
- **The tab in the strip.** `RETIRED_CM_TABS = ['gajjala_1m']` / `isRetiredTab` in `frontend/src/lib/chartMaps.ts`
  hide the button from the Chart Maps strip.

## WHAT STAYS

- **The 👀 Watch's 1-minute charts, by his call.** Its bars never ran through the 1-minute page's pass: the Watch
  reads its own 1m / 3m / 5m frames inside its own minute loop (`gajjala_watch/loop.py`, spawned by
  `run._spawn_watch`, gated by the Watch's own switch). Unchanged: the loop, the 9/21 EMA cross alert (GG5's 🧠 kind),
  `FRAMES` / `AXIS_FRAME` / `PUSH_FRAMES`, the live tick.
- **The 🤖 auto names** — now from 🚩 5-min and 🧪 only (the active sources drop `gajjala_1m`); an entry stored earlier
  with "🚩 1-min" still prints its words (history).
- **The ⤢ 15m / 5m / 1m card frame.** Its 1-minute view used to come from the page's own read doc. While the page is
  retired it reads the 👀 Watch's stored 1-minute tile of the SAME session for names on the Watch (his list plus the
  🤖 auto names) — ONE stored read, no fetch, no write. A name not on the Watch prints served words in the 1-minute
  slot ("… the 1-minute page retired 2026-11-18 by your call; a card's 1-minute view now comes from the 👀 Gajjala's
  Watch, and SYM is not on it"); its 15m / 5m charts stay intact. A prior-session Watch tile never draws as today.
- **Every other 1-minute bar surface** — untouched.
- **The route and the 🏁 history.** `/chart-maps?tab=gajjala_1m` still routes (hidden from the strip, not removed). With
  no `sub` and no `focus` it opens on its 🏁 Track record WITH the today read on the first GET (one helper,
  `tab.default_sub`, read by `resolve_sub` and by the route). The title and honesty say RETIRED 2026-11-18 and quote
  him; the board carries `variant.retired = {on, text}`. The `?focus=SYM` deep links keep the 2026-10-27 resolution.
- **The collections.** Every `gajjala_1m_*` collection stays; `passes` / `reads` / `state` expire by their existing
  TTLs, `potentials` / `ledger` / `alerts` / `replay` are kept. Nothing is purged.
- **The nightly grade.** `nightly.grade_1m()` still grades rows that are pending; no new row joins after 2026-11-17.
- **The two kinds and the keep-set.** `gajjala_1m_setup` and `gajjala_1m_potential` stay in `OWNER_KEEP_SET` and stay
  toggleable on /notifications; their detail leads "RETIRED 2026-11-18" and still states the LIVE SINCE 2026-10-29
  fact. The switch stops every send, so the toggle rings nothing.
- **🚩 5-min and 🧪 Audited bytes.** Not one byte: the GG5 WRITES and BOARD goldens are not regenerated.

## HOW TO TURN IT BACK ON

1. One word in `backend/chart_maps/gajjala/constants.py`: `GAJJALA_1M_ENABLED = True`.
2. Drop `'gajjala_1m'` from `RETIRED_CM_TABS` in `frontend/src/lib/chartMaps.ts` (the strip button returns).
3. Deploy:

```bash
./deploy-cheetah-main.sh api cron frontend
```

The words, the default sub, the push paths and the spawn all follow the switch back. The tests that pin how the page
RAN 2026-10-27 to 2026-11-17 run under an ON fixture, so the return is proven. The ⤢ card frame needs nothing: when the
page's own 1-minute read doc exists again, it leads by itself and the Watch fallback only fills an empty frame.

## WHAT WAS NOT DONE + HIS CALLs (defaults built are marked; none decided here)

1. The history surface — DEFAULT BUILT: the old route stays, hidden from the strip, reachable at
   `/chart-maps?tab=gajjala_1m`, opening on its 🏁 (with the today read) with a retired title / honesty. NOT built: a
   line on 🚩 5-min's 🏁 (would move the GG5 BOARD golden). Say the word if he wants the line there (= a dated BOARD
   regen).
2. `OWNER_KEEP_SET` — DEFAULT: unchanged (EIGHT; the switch already stops every GG1 send). Removing
   `gajjala_1m_setup` / `gajjala_1m_potential` = a keep-set change + `owner_prefs_apply` run + re-pins
   (`test_push_owner_keepset`, `Notifications.keepset.test`, contracts).
3. Notifications page — DEFAULT: the two kinds stay, toggleable, their detail leads RETIRED (and still states the LIVE
   SINCE 2026-10-29 fact). "Not toggleable / removed" = `DISABLED_ALERT_KINDS` = forces #2.
4. `/alerts` rows — DEFAULT: the two GG1 pass rows stay in their own strip and read stale / amber from 04:06 ET (the
   2026-10-27 design for the switch off). Options: a served "retired 2026-11-18" word in place of stale
   (alert_status `_daily`-style `schedule`, a payload-shape change pinned BE + FE) or dropping the rows (`PASS_KINDS` +
   `GG1M_PASSES` + contract re-pins).
5. `sw.js STICKY_KINDS` keeps `gajjala_1m_setup` (contracts pin it; nothing sends) — dropping it = his word + a
   contract re-pin.
6. `push/recent.py` — old `gajjala_1m_potential` items keep linking to `?tab=gajjala_1m` (the retired page). Pointing
   them at the Watch instead = his word.
7. `ema_blink.py` `TAB_KEYS` keeps `gajjala_1m` (a dot for a hidden tab; 0 after today) — removing it = his word
   (contract / tests pin `TAB_KEYS`).
8. The 📋 All strategies table on the retired page (`tab.table_on(GG1)`) still lists the last pass's stale rows under
   the retired title — hiding it = his word.
9. Mongo: `gajjala_1m_{passes,reads,state}` expire by their TTLs (30 d / 14 d); `gajjala_1m_{potentials,ledger,alerts,
   replay}` are kept forever by design — purge or export = his word (never done).
10. Crontab: no GG1 line exists; nothing for him to edit. The `GAJJALA_1M_ENABLED=0` env line is NOT needed (the
    constant governs) — adding it anyway = his word.
11. Re-use of the 1-minute page's ≤ 60 fetches a minute budget elsewhere (e.g. more Watch names, or a 2-minute Momo —
    DECLINED 2026-11-12, never re-proposed) — not proposed.
12. A deeper read of WHY the 1-minute A+ lost (17 W / 23 L, −6R; all-time 21 / 28) — nothing measured; a study = a new
    pre-registration (Rule #10), his word first.
13. The Watch's `AL.is_fresh(…, V.GG1)` freshness clock and lease numbers (55 s / 0 s) are GG1 constants reused by
    name — unchanged; renaming them to Watch-owned names = cosmetic, his word.
14. ⤢ card frame's 1-minute view for names NOT on the 👀 Watch — DEFAULT BUILT: served words ("the 1-minute page
    retired 2026-11-18 … SYM is not on it"); the 15m / 5m charts intact. Options, his word: (a) one fresh Massive
    1-minute read per card tap (a NEW cost during RTH; a second Massive client has kicked the live stream before;
    breaks the card-frames "fetches nothing" contract — a dated re-pin), or (b) add the tapped name to the Watch (he
    can do that today with the Watch's own add; then the 1-minute view fills within a minute). Not proposed: the GG5
    pass fetching 1-minute bars (moves the GG5 WRITES golden).

## eod-audits that read the 1-minute record (outside the repo — LIST ONLY, not edited)

- `eod-audits/research/2026-11-11_track_record_patterns/` — `analyze.py`, `diffs.py`, `day_indicators.py`,
  `rows.json`, `critic_rerun/*`, `critic_scratch/perm_rows.py`, `report_fix/cost_of_tags.py` read `gajjala_1m` rows.
- The nightly `scripts/track_record_snapshot_probe.py` (its `gg1` page) keeps snapshotting a frozen record.
- The Champions EOD audit is 🚩 Gajjala 5-min only since 2026-11-16 — unaffected.

## Where it lives

- Spec: "Retire the 🚩 Gajjala 1-minute page (GG1), reversibly — 2026-11-18" (session scratch, not in the repo):
  engine + words + route, the 👀 Watch + ⤢ card frame, the frontend, these docs.
- Code: `chart_maps/gajjala/{constants,variant,run_1m,run,on_demand,alerts,potential,tab}.py`, `chart_maps/api.py`
  (the gajjala-1m route), `supply_demand/rules_info.py`, `chart_maps/gajjala_watch/{auto,payload}.py`,
  `chart_maps/gajjala/card_frames.py`; FE `lib/chartMaps.ts`, `pages/ChartMaps.tsx`, `lib/gajjala.ts`,
  `pages/Notifications.tsx`.
- Tests: `backend/tests/test_gajjala_1m_retired_2026_11_18.py`, `backend/tests/test_gajjala_watch_1m_retired_2026_11_18.py`,
  the dated additions in `backend/tests/test_gajjala_card_frames_2026_11_16.py`, FE
  `pages/ChartMaps.retired_1m.test.tsx` and `lib/chartMaps.retired.test.ts`.
- Earlier docs, each with a dated note: `docs/gajjala/one_minute_page_2026_10_27.md`,
  `docs/gajjala/card_three_charts_2026_11_16.md`, `docs/notifications/owner_keepset_2026_09_20.md`.

UNMEASURED. Not advice.
