# 🔔 Long Term — Pankaj zone reaches + the weekly digest push (2026-11-12)

Spec: scratchpad `pkzone/spec.md` revision 2 (WP-BE-LT). Code: `backend/long_term_list/zone_watch.py` (the pass),
`store.py` (latch + session state), `sources.py` (`pankaj_closes(..., before=)`), `words.py` (every sentence),
`push.py` (the digest, live), `payload.py` (`zones.alert`), `api.py` (the GET reads the stored session doc),
`backend/sepa/cli.py` (the hook in `alerts`). Scripts: `backend/scripts/long_term_zone_probe.py` (read-only dry pass),
`backend/scripts/long_term_zone_reach_rate.py` (the rate below). UNMEASURED — Pankaj's zones are his, not a signal.

## His words (verbatim)

- 2026-11-12: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long term tabs in
  general" — reverses his 2026-09-08 "Remove all of Pankaj's alerts" for HIS ZONES on the 📅 🧭 list ONLY.
- 2026-11-12 (the Long Term tab): "Weekly and if something gets dropped let me know when to like is Sales drop or Stage
  2 to Stage 3 or stage 4 changes." — turns the held digest push on.

## One kind

Both pushes use ONE owner keep-set kind `long_term` (`constants.KIND`): the device `tag` keeps them apart
(`long_term:zone:<session>:<SYM>:<zone>` vs `long_term:<ISO week>`). One toggle mutes both (HIS CALL #6). The kind is
registered in the push stack by WP-BE-KIND (`push/subs.py`, `push/hooks.notify_long_term`, `market_hours/gate.py`).

## What "reached" means

A 🧭 name reaches one of Pankaj's zones when, on a 5-minute `sepa.cli alerts` pass (09:00–16:30 ET, no crontab edit):

1. its last trade from the ONE `prices.bulk_snapshot` of the 40 names is stamped TODAY (ET) and priced (a finite
   number > 0 — `extended_print` lets NaN through, so `criteria._num` guards it), and
2. that price sits inside the zone by `criteria.zone_read` — the /pankaj page's `setup_status` and its
   `PANKAJ_ZONE_PAD_PCT` (0.5%) pad, the ONE engine the tab's at-zone strip already uses, and
3. the PREVIOUS market day's close sat outside that zone. The baseline is `sources.pankaj_closes(..., before=session)`
   (one cache find; bars dated before the session, so the 16:30 pass never compares against today's own bar) and it
   must be dated `supply_demand.key_levels.prev_market_day(session)` — the house helper. A missing close
   (`prior_basis "none"`) or an older one (`"stale"`) cannot reach; the tab says how many names are stale
   (`zones.alert.stale_text`).

By design a name that closed inside a zone does not ring until it closes outside and comes back (HIS CALL #1).

## The latch and the log (critiques C1 / C2)

- `long_term_zone_latch` — INSERT ONLY, `_id` `"<session>|<SYM>|<zone>"`, inserted BEFORE the send: the push gate. A
  duplicate insert = no send and NO write. Never updated, replaced, deleted or retaken (a retake would allow a second
  send). Restart-safe: nothing on the ring path lives in memory.
- `long_term_zone_state` — one doc per ET session: the latest pass read (`$set` each pass: rows, reason, counts,
  `prev_session`), every reach of the session in `reaches.<SYM|zone>` (conditional `$set` on the field not existing —
  first write wins, so the first time and price are kept) WHATEVER the push reason, and `results.<SYM|zone>` written
  ONCE by the pass whose latch insert succeeded (pushed / no_target / failed) or failed on a store error (no_store — a
  later pass whose insert succeeds sends and overwrites it). No array appends anywhere.

## Gates, in order (`zone_watch.run_pass`, never raises)

1. `CHEETAH_IGNORE_HOLIDAY` override → nothing read, written or sent.
2. Closed day (`market_hours.gate.closed_reason`: weekends + `ALL_HOLIDAYS`) → nothing read, written or sent.
3. Seed unreadable → nothing.
4. ONE snapshot + ONE close read + the previous market day.
5. Pass reason (first that applies): no snapshot · outside `zone_edge.push_window` (04:00–20:00 ET, his 2026-09-08
   "Make phone push also pre and post market") · `ZONE_PUSH_MODE != "live"` · kind not in `subs.default_prefs()` ·
   no sender hook · dry run · no store.
6. The log (every reach, the pass reason as `push_reason`) — skipped only on a dry run or with no store.
7. The push, only with no pass reason: latch insert → one owner-scoped send (`hooks.notify_long_term`, owner =
   `subs._owner_email()`); never the all-devices broadcast.

Body: `🔔 TSM reached Pankaj's Agg zone` / `TSM 405.00 · Pankaj's Agg zone 400–410 · his Tier A · ZT 8.8` + "Pankaj's
zone from his sheet — not a signal. Rings once per name, zone and session." Pre-market / after-hours prints carry
" · pre-mkt" / " · after-hrs". No "buy" in any body; his sheet's action column is never copied; no per-name item
list on the payload (critique C5 — the feed renders the body as is).

## The tab (`zones.alert`, owner payload only)

`title`, `live`, `as_of_text`, `now` (who sits inside a zone now — the latest pass's rows when it belongs to today's
session and the house clock is not closed, else the latest closed bar, labelled "At the MM-DD close — no live read
now"), `empty_text`, `reason`, `stale_text`, `push_text`, `log_title`, `log` (the session's reaches with ET time and
price; `push_text` = the stored result, else why it was not sent, else "push result not recorded"),
`log_empty_text`. The GET reads the session doc with one find — never a fetch, never a snapshot, never the latch.
The old `at_zone` strip stays in the payload for back-compat.

## The weekly digest push (critique C6)

`DIGEST_PUSH_MODE = "live"`. Ring set unchanged (`RING_KINDS`: stage drop 2→3/2→4, sales drop, 🌱 started moving —
there is no 🔄 started-moving event, HIS CALL #2), body cap unchanged (6 lines + "+N more on the tab"), one push per
ISO week (`digest:<week>` claim). The push-hours window is read on the WALL clock at send time (`push._wall_et`), not
the weekly run's start clock. A zone line never rings the digest (HIS CALL #3).

## How often would it ring? (critique C3)

A frequency, not an edge claim — no placebo applies. Replay of today's 113 zones over the last 60 sessions, 0.5% pad,
prior close outside, once per name / zone / session, bootstrap 95% CI over sessions (5,000 resamples, seed 7).
**Ship-gate re-run 2026-11-13 ~01:35 ET (main session; throwaway container, worktree mounted read-only, cache only;
sessions 2026-08-21 → 2026-11-12, 40/40 names with frames, 113 zones) — identical to the planner's run:**

| read | per session | 95% CI | per week | max in a day | days with none |
|---|---|---|---|---|---|
| close inside (lower bound) | 1.70 | 1.35–2.08 | 8.5 (6.8–10.4) | 7 | 15 of 60 |
| day range touches (upper bound) | 3.68 | 3.20–4.22 | 18.4 (16.0–21.1) | 10 | 2 of 60 |

Caveats: zones applied in hindsight (today's sheet over 60 past sessions); the live pass samples the last trade every
5 minutes 09:00–16:30 incl. thin pre-/after-hours prints, so the real rate sits between the two rows. Busiest names
(day range): CLS 24, META 20, TSM 14, NVDA 12, BSX 12 of 60 sessions; busiest days 10-30 and 11-05 (10 each).

Re-run (read-only, cache only, outside RTH, throwaway container — spec §5.4):

```bash
docker run --rm --cpus 2 --memory 2g --network cheetah-market-app_default --env-file /Users/ajay/clinet-test/cheetah-market-app/backend/.env -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/.wt-basket/backend:/app:ro -v /private/tmp/claude-501/-Users-ajay-clinet-test/2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/pkzone/probe:/out -w /out cheetah-api:latest python -u /app/scripts/long_term_zone_reach_rate.py --sessions 60 --boot 5000 --seed 7 --out /out
```

## What is NOT built

- No alert for the /pankaj page's own picks (his 09-08 removal stands for them, HIS CALL #10); no `pankaj_alert` kind,
  no `sepa/pankaj_alerts.py`.
- No per-pass or daily cap (HIS CALL #4); no re-send of a latched reach whose send found no device (HIS CALL #9).
- No polling on the tab; no live snapshot on the GET.
- Half-day sessions: `zone_edge.session_state` uses a fixed 16:00 close, so 13:00–16:00 prints on a half day are tagged
  RTH. Cosmetic.

## HIS CALL (spec §7)

1 what "reached" means (prior close outside vs once a session vs pass-to-pass) · 2 🔄 started moving does not exist ·
3 zone reaches stay out of the digest's ring set · 4 burst cap (the measured rate above) · 5 hours (pre-market and
after-hours prints can ring, tagged) · 6 one toggle mutes both · 7 keep-set 7 → 8 · 8 the 0.5% pad now rides a push ·
9 no re-send · 10 scope = the 40 🧭 names only · 11 the Notifications row is public.
