# Industry-Group Leadership & Laggard Tagging — Methodology

**Module:** `backend/sepa/group_leadership.py`
**Source of truth:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013),
**Chapter 6 "Categories, Industry Groups, and Catalysts," pp. 95–116.**
**Status:** additive / DISPLAY-only (no scoring change). Shipped 2026-06-09 from
the book re-audit's #1 finding; see `docs/rfcs/001-industry-group-leadership.md`.

---

## Why

> **Book p.102:** *"You should concentrate on the top two or three stocks in a
> group: the leaders in terms of earnings, sales, margins, and relative price
> strength. This is especially true if the industry group is a leading sector
> during a bull market."*
>
> **Book p.108 ("Stay Away from the Laggards"):** *"A laggard is a stock that
> belongs to the same group as the market leader but has inferior price
> performance and in most cases inferior earnings and sales growth… Don't be
> tempted by a stock with a relatively low P/E or one that hasn't appreciated as
> much as has the leader."*

The scanner ranks RS as a **universe percentile** (`rs_rank`), so it cannot tell
the *leader of a leading group* from a *laggard riding the group's draft* — both
can land the same percentile. This module re-ranks RS **within each industry
group** to surface that distinction.

## What it computes (per scan row, all additive)

| Field | Meaning |
|---|---|
| `industry` / `sector` | yfinance tags via `companies.store` cache (same source as `moat_peers`) |
| `group_rs_rank` | 1 = strongest RS in its industry group (null if ungrouped) |
| `group_size` | number of scanned members in the group |
| `group_leader` | `True` if top-N **and** not a laggard (the "top two or three", p.102) |
| `is_laggard` | `True` if RS trails the group's strongest by ≥ the gap (p.108) |
| `group_leader_symbol` | the group's #1 RS name (what a laggard trails) |

**Leader and laggard are opposite ends, not just rank.** A rank-2 name is a
*laggard*, not a leader, if it trails the group's strongest by a wide margin
(p.108). So `is_laggard` is gap-based and rank-agnostic; `group_leader` requires
both top-N rank **and** closeness to the top. The two are mutually exclusive, and
a mid-pack name can be neither.

## Configured thresholds (book gives the CONCEPT, not these numbers)

Locked in `tests/test_sepa_contracts.py::test_group_leadership_constants_locked`.

| Constant | Value | Rationale |
|---|---|---|
| `GROUP_LEADER_TOP_N` | 3 | "top two or three stocks in a group" (p.102) |
| `LAGGARD_RS_GAP` | 20.0 | RS points below the group's strongest = laggard. Configured — the book is qualitative ("inferior price performance"); 20 is chosen, not a Minervini number. |
| `MIN_GROUP_SIZE` | 2 | need ≥2 scanned members for a leadership contest; a singleton gets null leader/laggard. |

## Group source & coverage

- Per-symbol **`industry`** (≈150 fine-grained groups, e.g. "Semiconductors") from
  the yfinance company snapshot cached in Mongo (`companies.store`), read via the
  new **cache-only batch** `store.get_many_cached()` — it NEVER calls yfinance, so
  it cannot slow the daily scan or trip a rate-limit.
- Names with no cached industry, or industry groups with a single scanned member,
  get **null** group fields — graceful degradation, never faked (Rule #1).
  Coverage grows via `store.get()` / `backfill_descriptions`. On the 2026-06-09
  scan, coverage was 105/105.

## How it's wired (DISPLAY-only, v1 untouched)

`scanner.scan()` (both full + fast paths) calls `group_leadership.annotate(results)`
as an **additive post-pass** right after ranking — it reads only `symbol` +
`rs_rank` and writes the fields above. It does **not** read or change `score`,
`SCORE_WEIGHTS`, `is_candidate`, or `is_buyable`. Per `SEPA_CONTRACTS.md` §12 these
are optional fields the formula does not read; `test_group_leadership.py`
asserts the annotation leaves `score`/`is_candidate` byte-identical.

Laggard policy (user, 2026-06-09): **caution chip only** — laggards are flagged,
never demoted or excluded. Any future *scored* use is a SEPA-v2 decision (RFC 001).

## What we do NOT do (stated, not silently dropped)

- No change to v1 score / gates / RS weight.
- No "leading group" (top-of-sector) weighting yet — only within-group leadership.
- The six stock categories (p.95) and turnaround/cyclical tests (pp.104-107) are
  separate and remain unimplemented (tracked in RFC 001).
