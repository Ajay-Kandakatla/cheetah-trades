# 📅 Long Term tab — the weekly read, the store, the endpoint (2026-11-12)

His words (2026-11-12, ~21:00 ET): "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I am asking you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."

And (~21:20 ET): "Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."

This doc covers the run side (spec revision 2, WP-RUN): `backend/long_term_list/store.py`, `weekly.py`, `push.py`, `api.py`, the hook in `backend/sepa/context_refresh.py`, the router line in `backend/main.py`, the rules-panel section in `backend/supply_demand/rules_info.py` and the probe `backend/scripts/long_term_list_probe.py`. The criteria are in `long_term_criteria_2026_11_12.md`, the sources in `long_term_data_2026_11_12.md`, the page in `long_term_tab_frontend_2026_11_12.md`.

**UNMEASURED.** A saved list kept up to date. None of these lists is a buy signal.

## The endpoint — `GET /chart-maps/long-term`

- **Owner only (C10, HIS CALL §7 #11).** `ollama_chat.api.is_primary_admin` of the forwarded `X-User-Email` (`auth.maybe_current_user`), the gajjala pattern in `chart_maps/api.py`. Anyone else — another email, no email, or a direct call that receives the `Depends` object — gets exactly `{state: "owner_only", reason, title}` with HTTP 200. Nothing is read for them: no seed, no Mongo, no cached close.
- **Owner:** `payload.build_payload(seed, baseline, runs, forward_docs, zone_closes, now=, owner=True)`, NaN-scrubbed (`growth.api._scrub`), run in `asyncio.to_thread`. Reads the stored runs + forward docs and ONE request-time cache read: `sources.pankaj_closes` (the 40 🧭 names, one `bulk_cached_frames` find, closed bars only). The GET never builds a week.
- States: `seed_only` (no run yet — every saved row from the at-save baseline), `ready` (the latest run doc), `error` (+ reason: the seed's sha changed, or a build raised). Every state answers HTTP 200. No Mongo → `seed_only`.
- Payload keys: the §3.10 contract, pinned by `backend/tests/fixtures/long_term_list_payload_golden.json` (WP-CORE).

## Schedule and hook

- No crontab line (a deploy does not ship the crontab). `context_refresh.after_scan(kind)` — called by `sepa.cli scan` / `fast-scan`, i.e. the 16:30 ET `fast-scan --mode broad` — calls the fenced `_long_term_hook(kind)` after its summary log line, before `return s`. Its return value is unchanged.
- `weekly.spawn_after_scan(kind)`: `eligible(now)` (no Mongo) → pytest guard → `chart_maps.gajjala.run_1m._popen([python, "-m", "long_term_list.weekly", "--after-scan", kind], "long_term_list_weekly")` — detached, a new session, no inherited descriptors. The scan process never holds the 24 MB scan + 📉 build of this run.
- `eligible(now, force=False)`: `LONG_TERM_LIST_WEEKLY=0` → off (even forced) · `CHEETAH_IGNORE_HOLIDAY` active and not forced → refused · closed day (`market_hours.gate.closed_reason` at noon ET, zoneinfo clock, never the gate's fixed −4) · not the last trading day of the ISO week (every later day of the week closed: Thursday before Good Friday counts, Thanksgiving week runs Friday) · before `constants.RUN_AFTER_ET` (= `scanner.SEPA_RERATE_ET`, 4:30 PM ET). `force` (`--run-now`, the probe) skips the calendar and the clock.
- The session a run reads: today once open and past 4:30 PM ET, else the last open day before. The ISO week id is the session's week.
- Missed week (host asleep at 16:30 Friday): no automatic catch-up (§7 #9). Recovery, off-RTH, in the cron container: `python -m long_term_list.weekly --run-now`.

## Idempotency and the collections (all fenced; Mongo down → not run, never a raise)

| collection | writes | content |
|---|---|---|
| `long_term_list_runs` | INSERT ONLY, `_id` = ISO week (`2026-W46`) | session, trigger, built_at(_iso), duration, timings, per-source `{ok, reason, as_of, n}`, `names` (all 109: stage, sales with quarter end + read date, sector, `legs` per chip, `qualifies`, 🧭 `zone_read`, `flags`), `top` (each screened list's strip), `top_read`, `events`, `digest`, `constants` |
| `long_term_list_forward` | INSERT ONLY | `_id: "base"` frozen once `{session, kind: "open", prices, no_base, pool_prices, pool_no_base}` + one point per ISO week `{at, list_pct, per_category, per_symbol, rsp_pct, spy_pct, n_sessions, ci, placebo, n_stale, n_carried, n_names, backfilled}` |
| `long_term_list_claims` | insert = claim; state updates | `run:<week>` (claimed → done / failed), `digest:<week>` (only when the push is live) |

- A second run in the same week (cron or `--run-now`) → "already ran this week (2026-W46)", one run doc.
- A run that raises marks its claim `failed` + reason and returns `{ran: False, reason}`. A failed claim is retaken ONCE by a conditional update on that state, so `--run-now` can redo a crashed week; a `claimed` / `done` claim is never retaken.
- `--dry-run --out PATH` builds the week and writes the JSON; it claims, writes and pushes nothing.

## What a run does

seed + baseline + prior runs → previous flags (the latest run, else the baseline's) → `sources.load_all` → `facts.build` → per screened list `criteria.pick_top` = **this week's top** (≤ 10, sector cap 3, 🔥 2; ✨ `new` = not in the last strip that READ that list; week 1 compares with the seed's own names) → per saved name: `criteria.legs` + `qualifies` per chip, 🧭 `criteria.zone_read`, `absent` = sources it was read in last week and not this week → `notices.detect` → `notices.digest` → the forward record → insert run → insert points → `push.send_digest` → claim done.

- **The saved set is the seed, every week (C6).** No run adds or drops a name; strip names never become rows. A name missing from every source is still a row (`not_read`).
- Notices and ring causes: `notices.py` (WP-CORE). Only `stage_drop`, `sales_drop`, `started_moving` (`constants.RING_KINDS`) can ever ring.

## The digest and the phone (HELD, C9, HIS CALL §7 #1)

`DIGEST_PUSH_MODE = "off"`: the digest is computed, stored on the run doc and shown on the tab ("Phone push is off — this digest shows here only."). `push.send_digest` returns "push off" before reading a pref, a claim or a sender. The held live path, in order: mode → kind registered in `push.subs.default_prefs()` → `CHEETAH_IGNORE_HOLIDAY` (a manual run never pushes) → closed day → `digest.rings` → the `hooks.notify_long_term_digest` hook exists → claim `digest:<week>` → ONE owner-scoped send to `subs._owner_email()`. Never `send_to_all`. The 8th keep-set kind is WP-PUSH's, not shipped.

## The forward record

- Base = the OPEN of the first session after 2026-11-12 (`forward.base_session` → 2026-11-13), frozen once — and only when the cached RSP frame holds that session (an empty base is never frozen). All 109 saved names get a base price or are listed in `no_base`. The placebo pool (`load_universe("full")` names, one `bulk_cached_frames` read per run, closed bars) is frozen in the same doc as `pool_prices`.
- One point per ISO week at its last trading day (≤ the run's session); missing weeks are backfilled (`backfilled: true`); a stored week is never rewritten. A missing bar → the last close ≤ that day (`n_stale`); a missing frame → the last stored price (`n_carried`); the name stays in the mean.
- Headline = the 74 screened names, equal weight; 🧭 its own per-category line. `n_sessions` = RSP closed bars from the base session to the point. Under 21 sessions (`REBALANCE`, a display gate) the tab shows "Too early" and no number; after, a by-name bootstrap 95% CI (2000 draws) and a random-names placebo band (1000 draws), seed 20261112.

## Rules panel (ℹ️)

`"long_term"` sits immediately before `"luk"` in `SECTION_KEYS`; picks = the eight screened lists' criteria from `words.rules_lines()`, stops = "No stop, no target, no size: a saved list and its weekly reads." (the panel requires a non-empty stops list — judgement call, the house line the 📉 / 🔻 sections carry), alerts = notices, schedule, phone push, forward method; note = `words.NOTE`. No 🧭 / Pankaj line: the panel is served to every user.

## Probe

`backend/scripts/long_term_list_probe.py` — the `fallen_tab_probe.py` read-only form (writes recorded no-ops, non-Mongo connects refused, provider calls stubbed). Runs `sources.load_all` with every source timed, `weekly.run(dry_run=True, force=True)` (pool-frames seconds + max RSS), and `build_payload(owner=True)` from the dry run ("ready") and from Mongo ("seed_only"). Outputs `/out/long_term_dry.json`, `/out/long_term_payload.json`, `/out/long_term_payload_seed_only.json`, `/out/long_term_probe_summary.json`. **Not run by WP-RUN** — the numbers land here after the main session's throwaway-container run (spec §5.5, outside RTH).

## Tests (WP-RUN)

`tests/test_long_term_list_store.py`, `test_long_term_list_weekly.py`, `test_long_term_list_push.py`, `test_long_term_list_api.py`, `test_long_term_list_after_scan.py`, `test_rules_info_long_term.py`.

## Not done here

- The probe numbers (main session, §5.5). The phone push (WP-PUSH held; §7 #1). Saving strip names (§7 #5). Opening the tab to other users (§7 #11). Automatic catch-up of a missed week (§7 #9).
- Every HIS CALL in spec §7 stays his.
