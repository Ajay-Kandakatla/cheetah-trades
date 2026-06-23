# The 3-C cheat tag — methodology

A qualifier tag for Minervini's **cup-completion cheat (3-C)** — the *earliest*
entry in his playbook — surfaced **only when the market is red and there are no
buyable breakouts**, because that is the exact condition the book describes it
for.

**Module:** `backend/sepa/cheat.py` (pure, stdlib, unit-tested).
**Attached by:** `sepa/scanner.py` → `_attach_cheat` (inside `_attach_conviction`,
both scan paths) → row fields `cheat_setup` (bool) + `cheat_detail` (dict).
**Display gate:** frontend only (red regime + no pivots — see below).
**NOT** an input to the Auto-Pilot engine — informational tag only.

## Why it exists, and why the gate

The cheat is Minervini's most **aggressive** entry: you buy *inside the base*,
before a volume-confirmed breakout. He literally named it a "cheat" because it
is *"the earliest point at which you should attempt to buy any stock"*
`TTLAC §7 (ebook p.132)`.

The book is specific about *when* it pays: cheats **develop during a general
market correction**, and *"the most powerful stocks will rally off this pattern
just as the general market averages turn up from a correction"*
`TTLAC §7 (ebook p.133)`. **Leaders bottom first** `TTLAC §7 (ebook p.123)`.

So the tag is gated to exactly that situation: a **red (risk_off) market** with
**no buyable pivots** (`buyable_count == 0`). When there is nothing to buy the
normal, conservative way, the cheat is where tomorrow's leaders are quietly
setting up — and the rest of the time the tag stays hidden, so it never clutters
the card. The gate is in the frontend (`isCheatVisible`); the backend always
computes the pattern.

## Detection (every threshold is a book number, TTLAC §7)

`cheat.detect(row)` reads fields the scanner already computes — no new market
math — and tags `is_cheat = True` only when **all** of these hold:

| pillar | rule | cite |
|---|---|---|
| Qualifier | `is_candidate` (Trend Template + liquid) | p.79 |
| Continuation | `pct_above_low ≥ 25` (prior advance of 25–100% / 3–36 mo) | p.133 |
| In a base | `10 ≤ pct_below_high ≤ 40` (constructive 10–40%; deeper is failure-prone) | p.119, p.133 |
| Volume dry-up | `vol_dryup < 1.0` (10-day avg below the 50-day) | p.226 |
| Tight coil | `vcp.has_base` and `≥ 1` good contraction (price tightness) | p.132, p.134 |
| Pre-breakout | **not** `is_buyable` (a confirmed breakout has graduated past the cheat) | p.132 |

`cheat_detail` also carries `off_high_pct`, `pct_above_low`, `vol_dryup`,
`good_contractions`, a human-readable `reasons[]`, and an optimum **shakeout**
bonus flag (the cheat drifting below a prior low, `TTLAC §7 (ebook p.134)`) when
the VCP undercut signal is present — never required.

## Boundary

This tag is **informational, for the human**. The deterministic Auto-Pilot
engine keeps taking only volume-confirmed breakouts and never reads
`cheat_setup` — the cheat is the aggressive, discretionary entry, and the engine
boundary (`test_brain_contracts.py` / `test_trading_contracts.py`) stays intact.

## Tests

- `tests/test_cheat.py` — canonical cheat detected; each pillar removed flips it
  off (non-qualifier, already-buyable, at-new-highs, too-deep, no prior advance,
  no dry-up, no coil); shakeout is a bonus not a requirement; missing/garbage
  fields never crash and always return the full schema.
- `tests/test_sepa_contracts.py` — `test_cheat_tag_thresholds_locked_to_ttlac_section_7`
  (book thresholds + detector locked) and `test_scanner_attaches_cheat_tag_to_rows`
  (both scan paths stamp `cheat_setup`/`cheat_detail`).
- Frontend: `frontend/src/lib/cheat.test.ts` — `isCheatVisible` only true in a
  red regime with zero buyable pivots (negatives for green/caution markets and
  for a market that still has breakouts).
