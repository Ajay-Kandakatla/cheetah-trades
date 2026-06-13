# Frontend testing

_Added 2026-06-13. Before this the frontend had no test harness — only
`tsc --noEmit` typechecking. This sets up unit tests so logic regressions on the
real-money surfaces fail before they ship._

## Stack

- **[Vitest](https://vitest.dev/)** — the Vite-native test runner (shares the
  app's `@vitejs/plugin-react` transform; no separate Babel/Jest config).
- **@testing-library/react** + **jsdom** — render components and assert on what
  the user actually sees.
- **@testing-library/jest-dom** — DOM matchers (`toBeInTheDocument`,
  `toHaveTextContent`, …), registered in `src/test/setup.ts`.

Config: `frontend/vitest.config.ts`. Tests live next to the code as
`*.test.ts` / `*.test.tsx`.

## Running

```bash
cd frontend
npm install        # one-time, pulls vitest + testing-library + jsdom
npm test           # run once (CI / pre-deploy)
npm run test:watch # TDD loop
```

## What to test (and how)

1. **Pure logic first.** The buy/sell/ranking math in `src/lib/*` is the
   highest-value, easiest target — no DOM needed. Example:
   `src/lib/pivotTiming.test.ts` exercises the full buy-timing state machine
   (GO / AT_PIVOT / COILING / WAIT) **and** the "don't buy" negatives (NONE /
   NOT_STAGE2 / EXTENDED), so a regression that flashes a green GO on a Stage-1
   base fails the build.
2. **Component render tests** for props-driven components. Example:
   `src/components/VolumeTrend.test.tsx` asserts the verdict + caption + the
   sparkline bar count, and that **no data renders nothing** (not an empty box).
3. **Always include the negatives.** Null/empty/missing props, the "do nothing"
   branch, the disabled/gated path. Most real bugs live in the edge, not the
   happy path.

## Conventions

- Build minimal fixtures with a local `mk(overrides)` helper and cast
  (`as unknown as SepaCandidate`) rather than filling every field — test only
  the inputs the unit reads.
- Components that depend on hooks/fetches (e.g. `PortfolioRail`, the rails) are
  better tested by extracting their pure logic, or with mocked hooks — don't
  hit the network in a unit test.
- Keep `tsc --noEmit` green too: `*.test.tsx` are typechecked with the app.

## Backend parity

The backend uses **pytest** in `backend/.venv` (host py3.9 lacks
pandas/numpy/requests). Same discipline — every behavioural change ships a
positive test + a negative/edge test + (for book formulas) a source-guard in
`tests/test_*_contracts.py`. Note: import package-level modules **standalone**
via `importlib.util` when the `portfolio`/FastAPI package trips py3.9 annotation
eval (see `tests/test_diagnosis_brain.py`).
