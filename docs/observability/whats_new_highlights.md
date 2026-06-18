# "What's new" feature highlights — methodology

_Added 2026-06-18. Ajay: "whenever we push a new feature, add a visual highlight,
and until I view it for the first time log it to analytics."_

A ✨ NEW highlight on freshly-shipped features that clears once the user has seen
it, with the unseen ones logged to analytics (in-house, same backend as the rest).

## The convention — register every feature you ship

When you ship a feature, add ONE entry to
`frontend/src/lib/newFeatures.ts`:

```ts
{ id: 'breakouts-beta', label: 'Beta column + low-vol sort',
  addedAt: '2026-06-17', route: '/breakouts' }
```

That's it for a **new page** — the nav badge is automatic. For an **in-page
enhancement** (a new column/panel), also drop `<NewBadge id="breakouts-beta" />`
next to the element. Entries auto-stop highlighting after `NEW_WINDOW_DAYS` (30).

## How it works

- **Registry** — `newFeatures.ts`: `{ id, label, addedAt, route? }`. A feature is
  "new" for a user if it's within the 30-day window AND not in their seen set.
- **Highlights** —
  - Nav: `NavLabel` shows a ✨ dot on a route that owns an unseen new feature.
  - In-place: `<NewBadge id label/>` shows a ✨ NEW pill next to any element.
- **Seen (per user, server-side)** — `useNewFeatures` loads the user's seen set
  (`GET /features/seen`). `NewFeatureWatcher` (mounted in `App`) marks a route's
  features seen after a 2.5s dwell (visiting the page = viewing it); clicking a
  `<NewBadge>` clears just that one. Seen state lives in Mongo (`feature_views`),
  so it follows the user across devices.
- **Analytics (the "log until viewed" part)** —
  - On load, the still-unseen highlights are logged as **impressions**
    (`POST /features/impression` → `feature_events {kind:impression}`).
  - First view logs a **viewed** event (`POST /features/seen` →
    `feature_events {kind:viewed}`). The gap (shipped − viewed) is queryable.

## Backend

`analytics/store.py`: `feature_seen_set` / `mark_feature_seen` (idempotent,
first-view detection) / `log_feature_impressions`. `analytics/api.py`:
`GET/POST /features/seen`, `POST /features/impression` (auth-gated to the user).

## Tests

- `backend/tests/test_feature_highlights.py` — per-user seen set, first-view
  idempotency, impression logging, soft-fail without Mongo.
- `frontend/src/lib/newFeatures.test.ts` — recency window + registry well-formed.
- `frontend/src/components/NewBadge.test.tsx` — shows when new, hides once seen,
  marks seen on click.
- Full FE suite stays green (NavBar/Breakouts render the badges).

## Notes / follow-ups

- Highlight semantics: visiting a page clears all of its new highlights after the
  dwell. A standalone "What's New" panel (list of recent features) could reuse
  `unseenNewFeatures()` if we want a dedicated surface later.
- Pruning old entries from `newFeatures.ts` is optional (they self-expire at 30d).
