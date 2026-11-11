# 🚩 "/" opens on Gajjala's tab — for the primary owner only (2026-11-10)

**Landing only.** No gate, rule, threshold, push, count, board or data change. The bare `/chart-maps` page, the tab
order and the menu are untouched. Frontend only; no backend file.

## His words

- Ajay 2026-11-10: *"Then default my landing page to Gajjala's tab in chartmaps on the app always."*
- Still binding underneath: 2026-09-07 *"Make chart maps default loading page for me on the app load. Also for
  everyone."* (Chart Maps leads both `LANDING_ORDER` chains in `frontend/src/lib/landing.ts`).

## What changed

- `frontend/src/lib/landing.ts`: `OWNER_LANDING_TAB: CmTab = 'gajjala'` (ONE literal, typed with `import type { CmTab }`
  so `chartMaps.ts` stays out of the entry chunk) and the pure helper `ownerLanding(target, isPrimaryOwner)`. When the
  viewer is the primary owner AND `pickLanding` picked `/chart-maps`, it returns `/chart-maps?tab=gajjala`; every other
  input comes back byte for byte (null stays null). The query is built with the same `tab` param
  `chartMaps.tabSearch` writes — `landing.test.ts` pins the two equal, so there is one URL convention.
- `frontend/src/App.tsx` `SmartLanding` (now exported for its test): also reads `useCurrentUser()` and waits for it.
  While `/auth/me` is loading → the existing `PageLoader` (never a wrong redirect). The call text
  `pickLanding(f.features, !!menu.is_admin)` is kept (contract "\"/\" lands on Chart Maps for everyone (2026-09-07)") and
  wrapped: `ownerLanding(pickLanding(f.features, !!menu.is_admin), !!user?.is_primary_admin)`. A failed or empty
  `/auth/me` ends loading with no user → today's target, never a stuck loader.
- Primary owner = `is_primary_admin` from `/auth/me` (ONE address, server-side). `is_admin` / `menu.is_admin` carry every
  house owner, co-owners included, so they are NOT used for this. No email in the bundle.

| Viewer | Winning landing feature | "/" goes to |
|---|---|---|
| Primary owner (`is_primary_admin` true) | chart-maps | **`/chart-maps?tab=gajjala`** |
| Primary owner | anything else (Chart Maps hidden) | today's target, no tab param (e.g. `/sepa-global`) |
| Co-owner (`is_admin` true, `is_primary_admin` false) | chart-maps | `/chart-maps` (unchanged) |
| Plain user / no `is_primary_admin` key | chart-maps | `/chart-maps` (unchanged) |
| Anyone, `/auth/me` still loading | — | the loader, no navigation |
| Anyone, `/auth/me` failed / empty | chart-maps | `/chart-maps` (unchanged) |
| Anyone, nothing accessible | — | the 404, never a redirect |

Side effect worth knowing: the catch-all `*` route and `FeatureRoute`'s "no access" redirect also pass through `/` →
`SmartLanding`, so for the primary owner those land on Gajjala's tab too.

## What did NOT change

`DEFAULT_TAB` (= `CM_TABS[0]`, the bare `/chart-maps` board), the `CM_TABS` order, `ChartMaps.tsx`, `chartMaps.ts`,
`cmPinnedTab.ts`, the menu's Chart Maps link, `LANDING_ORDER`, `pickLanding`, every backend file, every contract.

## Tests

- `frontend/src/lib/landing.test.ts` `ownerLanding`: the literal is `'gajjala'`, a member of `CM_TABS`, and `parseTab`
  keeps it; owner + `/chart-maps` → `/chart-maps?tab=gajjala`; the query equals `tabSearch(new URLSearchParams(),
  'gajjala')`. NEGATIVES: non-owner keeps `/chart-maps`; a non-chart-maps target (incl. `/chart-maps-x`, an
  already-tabbed path) never gets a tab param, owner or not; null stays null.
- `frontend/src/App.landing.test.tsx` (SmartLanding rendered in a MemoryRouter, hooks mocked): owner →
  `/chart-maps?tab=gajjala`. NEGATIVES: plain user → `/chart-maps`; no `is_primary_admin` key → `/chart-maps`; co-owner
  → `/chart-maps`; non-chart-maps winner → `/sepa-global`; user loading → loader, no navigation; features loading →
  loader; `/auth/me` failed → `/chart-maps`, no loader; nothing accessible → 404.

## HIS CALL (not decided here)

1. Co-owners, or everyone, landing on Gajjala's too (today: only his account).
2. The menu's "Chart Maps" link also opening Gajjala's tab (today: the bare board, `DEFAULT_TAB`).
3. A bare `/chart-maps` typed by hand also opening Gajjala's — note an iOS PWA that resumes its last page does not pass
   through `/`, so it reopens wherever he left it.
