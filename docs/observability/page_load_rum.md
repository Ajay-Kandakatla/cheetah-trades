# Page-load RUM (Real-User Monitoring) — methodology

_Added 2026-06-17. Ajay: "optimize the app for low internet speeds … is there a
way to audit visual painting of the page or add analytics like New Relic / Sentry
for frontend page loads to capture and improve."_

This is **step 1 of the performance effort: measure first, then fix.** It captures
real page-load + paint timings from real sessions so we can see which pages are
slow and how much worse they get on low-bandwidth links — then optimize where the
numbers point instead of guessing.

## Why in-house (not Sentry / New Relic)

The app already has an analytics pipeline (`usePageTracking → /analytics/event`,
`usageTracker → /usage/track`) that beacons to **our own backend + Mongo**. We
reuse it, so:

- **No third party** — none of this trading app's data leaves the server.
- **No account, no DSN, no cost** — Sentry/New Relic would need an external
  account + send data off-app. (Those remain an option if we later want error
  tracking / session replay; they'd be additive, not a replacement.)

## What's captured — `frontend/src/lib/perfReporter.ts`

Google's **web-vitals** lib (`onLCP/onINP/onCLS/onFCP/onTTFB`) — the standard,
spec-correct way to measure the Core Web Vitals (handles bfcache, LCP
finalization, CLS session windows, INP interaction grouping). Each sample carries:

- `metric` + `value` (LCP/INP/CLS/FCP/TTFB; CLS unitless, rest in ms)
- `route` — `location.pathname` (so we get per-page numbers)
- **`conn` / `downlink` / `save_data`** — the user's connection quality from the
  Network Information API. **This is the low-internet lens**: the summary splits
  every metric by slow (`slow-2g`/`2g`/`3g`) vs fast link.

Shipped via `navigator.sendBeacon` to `POST /analytics/perf`, flushed at
`visibilitychange→hidden` + `pagehide` (when web-vitals finalizes). Best-effort:
**never throws, silent on failure** — RUM must not affect the app it measures.
Wired once in `main.tsx` (`initPerfReporting()`).

## Backend — `analytics/store.py` + `analytics/api.py`

- `POST /analytics/perf` — ingest a capped batch (sendBeacon; public-ish like
  `/event/end` since beacons fire at unload). `record_perf` filters junk
  (unknown metric, NaN/negative/huge value), tags each with a **rating**
  (good / needs-improvement / poor, web.dev thresholds) + module, stores in the
  `perf_events` collection (180-day TTL, same as `usage_events`).
- `GET /analytics/perf/summary?days=N` — **admin-only**. `aggregate_perf` →
  `_summarize` (pure) returns **p50/p75/p95 per (module, metric)** and per metric
  overall, plus `poor_rate` and the **slow-vs-fast-connection split**.

The web.dev rating thresholds (`PERF_THRESHOLDS`) and the percentile roll-up are
the locked contract — see tests.

## How we'll use it

1. Deploy, let real sessions accumulate a day or two of samples.
2. `GET /analytics/perf/summary` → find the pages with the worst p75 LCP/INP and
   the biggest slow-connection gap (almost certainly `sepa` / ticker-details).
3. Optimize those data-driven (code-split, defer non-critical fetches,
   skeleton-first render, lazy charts), and watch the same metric drop.

A small admin viewing UI on the `/usage` (or a `/admin`) page is a fast follow;
for now the JSON summary is the source of truth.

## Tests

- `backend/tests/test_analytics_perf.py` — rating thresholds, percentile
  interpolation, the roll-up + slow/fast split, ingest filtering, soft-fail.
- `frontend/src/lib/perfReporter.test.ts` — a captured metric is queued with
  route + connection, beacons to `/analytics/perf`, degrades to `unknown`
  connection, and never throws on beacon failure.

## Out of scope (this slice)

- Sentry/New Relic (external; would need an account + your authorization to send
  data off-app).
- A custom SPA `route_load` timing (route-change → primary-data-ready) — the
  `route_load` metric + threshold are reserved in `PERF_THRESHOLDS`; the client
  hook is a follow-up.
- The admin viewing dashboard (JSON summary for now).
