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
- **Column reference (ⓘ)** — a *"What do these columns mean?"* info icon sits on
  the table itself (above it, right-aligned, so it's visible without horizontal
  scrolling on mobile). It opens a per-column legend covering every column:
  #, Ticker, # breakouts, Last, Price, Δ%, Vol %, Total Vol, Turnover, Stage,
  **Beta**, → R1/R2, Verdict — each with the Minervini p.203 cite where relevant.
  This is separate from the page-title ⓘ (which explains the page concept). Added
  2026-06-17. Every column header is also click-to-sort.
- **Beta** column (1-year daily volatility vs SPY) — tap the header to sort
  **low-volatility first**. Display-only; see `beta_methodology.md`. Added
  2026-06-17.
- **Verdict is confirmed on the fly** — if the persisted scan didn't annotate a
  row's `buy_verdict` (e.g. written by an older worker), `board()` recomputes it
  from the row's price-side fields (`buyable_verdict.compute`) rather than showing
  "verdict pending". ETFs still get no Minervini verdict. Added 2026-06-17.

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
