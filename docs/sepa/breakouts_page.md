# Breakouts page (`/breakouts`)

**Requested:** Ajay, 2026-06-16 — *"a page to track only breakouts and # of
breakouts, starting with the highest breakouts ... some passing Minervinis and
some not, and Pradeep Bondi, but mainly around breakouts."*

**Frontend:** `frontend/src/pages/Breakouts.tsx` · `hooks/useBreakoutBoard.ts`
**Backend:** `backend/sepa/breakout.py::board()` → `GET /sepa/breakout-board`
**Feature flag:** `breakouts` (FEATURE_CATALOG, owner-on via `added_in: 15`)
**Tests:** `backend/tests/test_breakout_board.py` · `frontend/src/pages/Breakouts.test.tsx`

## What it shows

Every name in the latest scan that has **actually broken out** (≥ 1
volume-confirmed breakout), ranked by **breakout COUNT, highest first**.

- **Breakout** = a close above the prior 21-day high on **> 1.5× the 50-day
  average volume** — Minervini, *Trade Like a Stock Market Wizard*, p.203. The
  count is `volume.analyze()`'s `breakout_count` (distinct breakouts over the
  trailing ~year); same definition already used by the card chip and the
  Leaderboard "Breakout leaders" board. This page does not recompute it.
- **Verdict overlay** — each row carries the combined **Minervini + Bonde**
  `buy_verdict` (see `buyable_verdict_methodology.md`), so the page shows *which*
  high-breakout names pass the book and which don't ("passing Minervinis and
  some not"). Filter chips slice the same breakout list:
  `All · ⚡ today · 🟢 Minervini+Bonde · Minervini ✓ · Minervini ✗ · Bonde ✓ · Bonde ✗`.
- **Summary strip** counts the pass/fail mix at a glance (total, today,
  both-pass, Minervini ✓/✗, Bonde ✓/✗).
- **⚡ today** flags names whose most recent breakout was the latest session
  (`days_since_breakout == 0`).
- Tapping a row → that name's **detail Breakout tab** (where each breakout fired
  on the price chart).

## Contract

`board()` is **display-only and additive** — it reads the persisted scan
(`breakout_count` from `volume.py`, `buy_verdict` from `buyable_verdict.py`) and
feeds no score. It introduces no new formula or threshold; it ranks and overlays
already-computed fields. The verdict only fills the Bonde pillar for enriched
(top-N) names; un-enriched breakout names show a Minervini-only verdict
(`sales pending`), never a faked one.

The board is empty until a scan runs with the breakout-count + verdict code (the
fields are written during the scan). Sort key: `(-breakout_count, -rs_rank,
symbol)` — deterministic ties.
