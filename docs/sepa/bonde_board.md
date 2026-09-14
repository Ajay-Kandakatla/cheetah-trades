# 📈 Bonde board

Ajay 2026-09-13: *"create me a Bonde tab. we already have his rules in the
analysis tab on individual ticker but I wanna see explicitly new ones getting
added in this tab … but I wanna see his stocks."*

Chart Maps tab `bonde`. **Nothing here re-derives Bonde** — every rule is called
from the module that already implements and cites it.

| What | Where it already lived |
|---|---|
| His 5% / 25% / 100% sales tiers | `sepa/sales.py` |
| The PASS rule | `sepa/buyable_verdict.py::_bonde_pillar` |
| The Episodic Pivot | `setups/episodic_pivot.py` |
| The sourcing | `docs/sepa/sales_confidence_methodology.md` |

---

## 1. Why the board is the INTERSECTION

Measured on the live scan the day it was built — this is what decided the shape:

| Leg | Count | Verdict |
|---|---|---|
| **Sales gate alone** | **1,051 of 2,076 (50.6%)** | Half the market. A description, not a selection. |
| **Episodic Pivot alone** | 50 setups; of the 32 in the scan, **11 have DECLINING sales** | A tape pattern. On its own it selects what his screen throws away. |
| **Both** | **12** | A board. |

Sales tiers underneath the gate: explosive 72, strong 317, steady 691, weak 227,
declining 265, unknown 504.

So **the sales screen is the universe and the Pivot is the entry** — which is how
Bonde describes his own process. ⚡ Pivots lead because that intersection is the
only part of this board that selects; the tiers below are a watchlist.

---

## 2. Whose numbers are whose

- **Bonde's own**, documented in his writing: the 5% floor (*"I take 5%"*), 25%
  preferred (*"you can use 25% plus"*), 100% explosive (his *"Sales 100% plus"*
  EP category, 2010). The methodology doc also lists the figures **widely
  attributed to him that failed source verification** (30% / 39% two-quarter /
  "MAGNA 53+" — they come from Deepvue / TradeZella / TraderLion, not Stockbee)
  and are deliberately not used.
- **This app's owner settings**, and the board says so: the Pivot's **8% gap on
  5× volume** (stricter than its PEG cousin because it has no earnings-calendar
  filter), and the **$1M base materiality floor** below.

---

## 3. The revenue-base defect

Caught on the live board before it shipped. Ranked on the raw percentage, the top
of the "explosive" tier was almost entirely arithmetic:

```
DBRG  +15,961%   year-ago quarterly revenue was MINUS $3,207,000
APLD     +877%   year-ago quarterly revenue was MINUS $33,300,000
QUBT   +9,000%   year-ago quarterly revenue was $61,000
FCUV   +1,811%   year-ago quarterly revenue was $35,330
```

`sepa/sales.py::_yoy` divides by `abs(base)`, so a **negative base returns large
positive growth** — a sign flip, not a ramp. Meanwhile the genuinely explosive
businesses ranked *below* the artifacts: PTGX $5.5M → $213M, LQDA $8.8M → $171M,
ONDS $6.3M → $83.8M.

**`sales.py` is not changed.** It is book-cited, locked by contract tests, and
read by the falling-knife gate on several other boards — moving its arithmetic
would move `sales.score` app-wide. The board handles its own ranking instead:

| `base_state` | Meaning | Effect |
|---|---|---|
| `non_positive` | Year-ago revenue ≤ 0 | Arithmetic, not a threshold. No percentage ranking, no dollar figure. |
| `too_small` | Year-ago revenue < **$1M** | This app's materiality setting, stated as such. |
| `ok` | A real base | Ranked on growth. |

Flagged names are **still shown**, with their percentage and their dollars —
hiding them would make the board disagree with his screen. They simply never
outrank a company with a real base. Every row prints `$base → $latest` beside the
percentage, because the dollars cannot lie the way a ratio can.

After the fix the tier reads: PTGX +3,749% ($5.5M → $213M), LQDA, ONDS, UMAC,
NUVB, RCAT, UUUU — real small-cap ramps, which is Bonde's territory. DBRG and
QUBT sit at the bottom with their numbers visible.

---

## 4. ✨ NEW — his explicit ask

`sepa/first_seen.py`, collection `bonde_seen`, 30-day window.

The subtle part: on the **first** build every name has a `first_seen` of now, so
a naive read badges the entire board. A `__meta__` row records when tracking
began, written with the **same timestamp** as that first cohort, and `newly_found`
uses a **strict `>`**. The first board therefore reports **zero** arrivals, which
is the honest answer — *"we have only just started looking"* must never render as
*"these are fresh finds"*.

Arrivals are recorded over **every name that passes**, not only those surviving
the per-section cap: a name that arrives into a capped tier has still arrived, and
recording only the visible ones would reset its clock each time the cap pushed it
off and back on.

`growth/tracker.py` has its own copy of this logic (written first, live on the
Explosive Growth board). It is **not** refactored — that board works and the user
gains nothing — but `tests/test_first_seen.py` asserts the two behave identically
on the same inputs, so the duplication cannot silently drift.

---

## 5. What building this found: every setup kind is stale

Not a bug — **his own rule**, finally working.

```
episodic_pivot  newest 413h    peg      newest 461h
bull_flag       newest 413h    orb      newest 326h
… zero fresh rows across all 18 setup kinds
```

`setups/universe.is_bull_regime()` gates every setup scanner. He explicitly chose
to sit out bear markets, and the gate reads `market_in_correction` (score 66.5) →
`False` → every scanner short-circuits and writes nothing.

It bites harder than it looks because **the gate was itself broken until
2026-08-31**: it imported a function that never existed in `sepa.market_regime`,
a bare `except` swallowed the ImportError, and it returned `None` ("cannot tell,
go ahead") on every call. The sit-out rule had never once fired. It was fixed,
and the fleet went quiet almost immediately after.

So the board **says so on the page**. An empty headline section with a structural
cause reads as broken otherwise, and "his entry setup is switched off because the
market is in correction" is itself the useful information.

---

## 6. Not measured

The Episodic Pivot has **never been measured** in this app — the pattern accuracy
ledger (`GET /patterns/accuracy`) tracks chart patterns (double_bottom,
cup_with_handle …), not setups. The board ships labelled as such, the same way the
ICT, Keltner and AMD tabs do. Nothing here gates a scan, fires an alert, or buys
in any lane.

---

## 7. Files

```
backend/sepa/bonde.py              the board, the base guard, the regime notice
backend/sepa/bonde_api.py          GET /bonde/board
backend/sepa/first_seen.py         the ✨ NEW ledger, generically
backend/sepa/board_metrics.py      warm list extended to Bonde names
backend/main.py                    router mount
backend/crontab                    40 17 * * 1-5 (arrivals), 45 17 (metrics)
backend/tests/test_bonde.py        13 tests
backend/tests/test_first_seen.py   7 tests incl. the drift guard
frontend/src/components/BondeBoard.tsx
frontend/src/components/BondeBoard.test.tsx   12 tests
frontend/src/lib/chartMaps.ts      CmTab, CM_TABS, TAB_META, isBoardTab
frontend/src/pages/ChartMaps.tsx   tab mount
frontend/src/styles.css            .bd-*
```
