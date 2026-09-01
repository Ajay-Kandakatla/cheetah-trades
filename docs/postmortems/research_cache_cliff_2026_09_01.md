# Postmortem: every Bonde-gated board empty at the open (2026-09-01)

**Symptom** (Ajay, Tuesday premarket): "Why is deep demand and undervalue
stocks empty" — Deep Demand showed 0 tiles, Under Value said "whole
universe (1 screened)". Gabbar Levels was equally starved.

**Root cause chain**
1. The Bonde sales gates read `sepa.research.sales_snapshot` (Mongo
   `sepa_research_cache`, TTL then 8 days) and correctly FAIL CLOSED:
   sales unknown = dropped, never passed.
2. The cache is refilled by ONE weekly cron (Sunday 20:00 ET,
   `research-refresh --mode broad`). The 2026-08-30 run never landed (the
   cron container from that night was replaced Monday morning; its logs
   are gone, so the precise failure is unrecoverable).
3. The entire cache was therefore a single batch from 2026-08-23. With
   TTL = cadence + 1 day, it crossed the TTL in ONE night: 3,642 fresh
   Monday evening → 21 by Tuesday 6am. Boards went from full to empty
   with no intermediate state.
4. The health check was fraction-aware but REACTIVE — it truthfully said
   "ok" at every Monday audit (the cache WAS fresh) and would only have
   warned after the boards were already dark.

**The scan itself was healthy** (1,756 symbols, 47 deep-demand matches
that morning) — the drop counter said it plainly: `dropped_no_sales_data: 47`.

**Fixes** (branch fix/research-cache-cliff-2026-09-01)
- `CACHE_TTL_SEC` 8d → **16d**: a missed Sunday now leaves 9 days of
  margin, and quarterly fundamentals at 16 days stale are a far smaller
  error than absent.
- `research.needs_refresh()` + `research-refresh --only-if-stale`:
  a **nightly Mon–Sat 20:30 ET catch-up cron** that is a one-line no-op
  while healthy and a full refresh the first night the SURVIVING-in-48h
  fraction drops under 60% — it fires on the Monday after a missed
  Sunday, not on the Tuesday after the cliff.
- `status()` now reports `expiring_48h`, and the health check warns
  PREDICTIVELY when most of the fresh set dies within 48h.
- Recovery: manual `research-refresh --mode broad` kicked 2026-09-01
  ~09:39 ET; boards refill progressively as names land.

**Tests**: tests/test_research_cache_cliff.py — the exact cliff shape
(all fresh, all expiring within 48h) must fire the catch-up and the
warning; TTL floor ≥ 15d; source guards on the crontab line + CLI wiring.

**Lesson** (same family as Rule #7): cache AGE is not cache SAFETY — a
weekly-batch cache needs its TTL ≥ two cadences and a predictive check
on time-to-expiry, or "100% fresh" and "0% fresh" are one night apart.
