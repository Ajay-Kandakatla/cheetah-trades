# RFC 001 — Industry-Group Leadership & Laggard Ranking (SEPA v2)

**Status:** Proposed (2026-06-09, from the Minervini book re-audit)
**Decision owner:** Ajay
**Recommendation:** build on a **SEPA v2 path**, do NOT touch the v1 score.

---

## Problem (the audit's #1 / only HIGH-severity selection gap)

Chapter 6 ("Categories, Industry Groups, and Catalysts") makes group leadership a
**central, quantified selection rule**, and the scanner implements **none** of it.

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
>
> **Book p.95:** stocks *"generally tend to fall into one of six categories:
> 1. Market leaders 2. Top competitors 3. Institutional favorites 4. Turnaround
> situations 5. Cyclical stocks 6. Past leaders and laggards."*

### What the code does today
- `backend/sepa/rs_rank.py` computes RS as a **percentile across the entire scan
  universe** — never relative to a stock's industry group.
- The scan row (`scanner.py` ~444-465) carries **no sector / industry label**.
  (`grep -i sector backend/sepa/scanner.py` → nothing.)
- No laggard detection (`grep -i laggard backend/sepa/*.py` → nothing).
- `pioneers.py` "themes" are technology buckets (AI infra, GLP-1…), **not** the
  six maturity categories and **not** an industry-group map.

**Consequence:** a *laggard riding a hot group's draft* and the *leader of that
group* can land the same RS percentile and the same score. The scanner cannot
distinguish "leader of a leading group" from "cheap also-ran," which is precisely
the distinction Ch.6 is built to make.

---

## Why this MUST be a v2 path (governance)

Per `SEPA_CONTRACTS.md` §12, **adding a new score component** and **changing the
`rs_rank` contribution / `is_candidate` gate** require *explicit sign-off + a
SEPA v2 path*; v1 stays untouched while the new signal is observed live for
weeks before any promotion. This RFC therefore proposes **additive fields + a
parallel ranking view**, not a change to the v1 `SCORE_WEIGHTS` or gates.

---

## Data feasibility (already in the codebase)

- **Per-symbol industry/sector tag:** `moat_peers.py` already reads yfinance
  `industry` + `sector` per ticker via `companies.store` (see its
  `find_peers()` — output already includes `"industry": "Semiconductors",
  "sector": "Technology"`). That same source gives every scan row a group label
  with **no new provider call**.
- **Curated thematic groups:** `supply_demand/sectors.py` has `SECTORS[*].sp_tickers`
  (e.g. `ai_chips → [NVDA, AMD, AVGO, …]`) — a hand-curated leading-group map we
  can use to mark "leading sector during a bull market" (p.102).
- **RS per name:** `rs_rank.rs_score(df)` already produces the raw blended return
  used for the universe percentile; group-relative ranking is a regrouping of the
  same numbers, not a new computation.

So the data is in hand; this is wiring + a v2 view, not a new pipeline.

---

## Proposed design (additive, v1-safe)

1. **Group label on the row (additive field, no scoring impact).** Add optional
   `industry` / `sector` to `CandidateRow` (sourced from `companies.store`, same
   as `moat_peers`). Documented under §3 "optional commonly-present fields."

2. **Group-relative RS leadership flag.** Within each industry group present in
   the scan, rank members by `rs_score`; flag the **top 1-3** as
   `group_leader` (p.102) and expose `group_rs_rank` (1 = strongest in group)
   and `group_size`. Additive fields only.

3. **Laggard flag (p.108).** `is_laggard = same group as a `group_leader` AND
   materially lower RS / price performance (threshold TBD, e.g. RS gap ≥ 20 vs
   the group leader)`. Surface as a **caution chip**, not a hard exclusion.

4. **Leading-group context.** Tag the row's group as a "leading group" when it
   ranks in the top-N groups by aggregate member RS (and/or appears in
   `sectors.py`), restating p.102's "leading sector during a bull market."

5. **(Optional, later) Six-category tag.** A lightweight classifier
   (`market_leader` / `top_competitor` / `institutional_favorite` / `turnaround`
   / `cyclical` / `laggard`, p.95) so category-specific rules (e.g. the
   turnaround +100% test p.104-105) can be layered later. Out of scope for v1 of
   the RFC; tracked here so it is not silently dropped.

6. **SEPA-v2 ranking view.** A parallel rank that blends the v1 score with the
   group-leadership signal (e.g. boost `group_leader`, demote `is_laggard`),
   rendered on a `/sepa-v2`-style view or as sortable columns, run **alongside**
   v1 for live observation. v1's list and score are untouched.

## Surfaces — where the signal shows up (Ajay 2026-06-09: "on the leaderboard as well")

The same additive fields should surface everywhere a candidate is rendered, not
just the scanner:

| Surface | How it inherits | Work needed |
|---|---|---|
| **SEPA scanner cards / detail** | `SepaCandidateCard` reads the additive row fields | add a `group_leader` / `is_laggard` chip + the `group_rs_rank` line |
| **Leaderboard — Cross Junctions** | returns **full candidate rows** (`SEPA_CONTRACTS.md` §11d) | chips appear **automatically** once the card renders them — zero backend work |
| **Leaderboard — main rank table** | `leaderboard.aggregate()` builds a **slim projection**, not a full row | **one-line pass-through** per field, exactly like the existing Ch.8 chip (`leaderboard.py:162` `"earnings_quality": (cur.get("fundamentals") or {})…`); then a `Group leader / Laggard` filter + a sortable **Group RS** column |
| **Portfolio / holding read** | reads candidate fields | a "laggard in its group" caution on holdings (optional) |

**Leaderboard ranking stays persistence-based.** Like the EQ chip
(`leaderboard.py:160` — *"the RANKING already reflects it via current_score"*),
group-leadership on the leaderboard is a **display + filter** signal by default;
it does **not** silently re-sort the board. A dedicated "group leaders only"
filter or a group-leadership sort is opt-in (and, if it ever feeds a score, that
is the v2 path, not v1). This keeps the leaderboard's meaning ("who's
consistently ranked") intact while letting you slice it by group leadership.

---

## Rule #4 deliverables (when built)

- **Behavioral test** — synthetic multi-group universe → correct `group_leader` /
  `is_laggard` / `group_rs_rank` assignment (e.g. a low-RS name in a strong group
  flags laggard; the top-RS name flags leader).
- **Source-guard** in `test_sepa_contracts.py` — lock the leadership thresholds
  (top-N, laggard RS gap) and cite p.102/108.
- **Methodology doc** `docs/sepa/group_leadership_methodology.md` — every rule
  with p.95-116 cites + an explicit "what we can't get" section.
- **Spec** — new additive fields in `SEPA_CONTRACTS.md` §3; the v2 ranking in a
  dedicated section; v1 §4 explicitly noted unchanged.

---

## Open questions for Ajay

1. **Group source:** yfinance `industry` (fine-grained, ~150 groups) vs `sector`
   (coarse, 11) vs the curated `sectors.py` themes — or a blend? Minervini's
   "group" is closer to **industry** than sector.
2. **Laggard RS-gap threshold** (20? 30?) — configured, not a book number.
3. **Does a laggard get demoted in the v2 rank, or only chip-flagged?** (The book
   says avoid them; a hard demote is stronger than a caution chip.)
4. Build the **six-category** tag now or defer?

## Out of scope (stated, not dropped)
- Any change to the v1 `SCORE_WEIGHTS`, `rs_rank` weight, or `is_candidate` gate.
- Turnaround / cyclical category-specific tests (p.104-107) — depend on the
  category tag (item 5), deferred.
