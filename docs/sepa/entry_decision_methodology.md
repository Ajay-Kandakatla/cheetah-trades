# Entry decision — the green **ENTER** verdict requires Stage 2

**Code:** `backend/sepa/entry_exit.py` (`build_entry_exit` → `_decide`) · `frontend/src/lib/pivotTiming.ts` (`pivotTiming`)
**Contracts:** `backend/tests/test_entry_decision_stage2.py` (behavioral + SMCI regression) · `tests/test_sepa_contracts.py::test_enter_verdict_requires_stage2` (source guard) · `frontend/scripts/contracts.mjs` (pivot-meter gate)
**Book:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013) — stage analysis **pp. 69–76**, Trend Template **p. 79**, buy-on-volume **p. 203** (printed pages; the repo PDF is offset +15).
**Status:** added 2026-06-02 to fix the SMCI "WATCH-but-ENTER" contradiction.

---

## 1. The rule — only buy Stage 2

Minervini's foundational discipline is **stage analysis** (Weinstein's four stages,
pp.69–76): you buy a stock **only while it is in a confirmed Stage 2 advance**.

| Stage | Phase | Action |
|---|---|---|
| 1 | Neglect / **basing** — sideways after a decline | **Don't buy.** Wait. |
| 2 | **Advancing** / accumulation | **The only place you buy.** |
| 3 | Topping / distribution | Sell / stand aside. |
| 4 | Decline / capitulation | Out. |

The actionable buy is the **Stage 1 → Stage 2 transition**: the stock breaks out of
its base above the pivot **on expanding volume** (p.203), *and* it satisfies the
8-point **Trend Template** (p.79) that operationally defines a Stage 2 leader. A
one-day volume pop *inside* a Stage 1 base is **not** that — it is exactly the kind
of false start the Trend Template exists to filter out.

## 2. The bug it fixes (SMCI, 2026-06-02)

The card carries **two independent "should I buy?" signals**:

1. `is_buyable` / the verdict + score (`scanner._is_buyable`) — correctly requires
   `trend.pass_all AND stage == 2 AND setup AND not-late AND liquid`. For SMCI
   (**Stage 1, Trend 5/8**) this was `False` → the card read **WATCH 66**. ✅
2. The green **ENTER** banner (`entry_exit._decide`) and the pivot-meter **GO**
   pill (`pivotTiming`) — both derived purely from *price-vs-pivot + volume*, and
   `_decide` checked stage **only to reject Stage 3/4**. SMCI's pocket-pivot pop
   with price at the pivot read `actionable + volume-confirmed → ENTER`. ❌

Result: the same card said **WATCH** (correct) and **ENTER** (wrong) at once.

## 3. The gate

A name is **buyable-eligible** iff it clears the strict scanner gate
`_is_setup_ready` — `trend.pass_all AND stage == 2 AND entry_setup AND not
late-stage AND liquid` (i.e. `is_buyable` minus the same-day-breakout clause; see
SEPA_CONTRACTS §5b/§5c). `ENTER` / `GO` may fire **only** for buyable-eligible names.

**Backend** (`entry_exit._decide`):

```
buyable_eligible = setup_ready  if setup_ready is not None  else (stage_num == 2)

# precedence: Stage 3/4 distribution → earnings → missed → below-trigger → chop →
if actionable and not buyable_eligible:
    Stage 1 / unknown → WAIT  "still basing (Stage 1) — not a confirmed Stage 2 advance"
    Stage 3           → WAIT  "Stage 3 (topping) — not a Stage 2 advance"
    else (Stage 2 but Trend Template not 8/8 / late) → HOLD_WATCH
if actionable and vol_ok:  → ENTER   # only reached when buyable_eligible
```

`build_entry_exit` receives `setup_ready` from the scanner at both call sites
(full + fast paths). Called standalone (no `setup_ready`), it falls back to
`stage == 2` so it still cannot greenlight a Stage 1 name.

**Frontend** (`pivotTiming`), mirroring the same gate so the meter never contradicts
the banner:

```
eligible = is_buyable === true || setup_ready === true || (setup_ready == null && stage.stage === 2)
…
else if (above && !eligible) state = 'NOT_STAGE2'   // "Wait · not Stage 2 yet"
else if (above && breakingOut) state = 'GO'
```

## 4. What does NOT change

- `is_candidate` / `qualifier` (the watchlist gate, p.79) — unchanged.
- `is_buyable` and `setup_ready` (scanner) — unchanged; this fix makes the
  *verdict banner + meter* agree with them, it does not move the gates.
- The buy mechanics (pivot ≤5% tight handle, 1.5× breakout volume, buy-zone
  ceiling) — unchanged; see `vcp_methodology.md`.
- A genuine Stage 2 breakout still reads **ENTER / GO** exactly as before.

## 5. Stop-loss levels are configured proxies, NOT the book's adaptive rule (owned deviations, 2026-06-09 audit)

The surfaced stops are fixed-percentage / structure-based proxies. Minervini's
actual stop discipline is **adaptive** and is **not** implemented; we flag the
gaps rather than claim book-fidelity:

| Surfaced stop | Where | Book says | Status |
|---|---|---|---|
| Flat **7%** hard cap | `analysis/trade_plan.py` `MINERVINI_HARD_STOP_PCT` | Stop = **½ × your real average gain** (p.299), monitored & adjusted over time (p.300) | Configured proxy — book's avg-gain rule needs the user's realized batting stats, which we don't track. |
| Tight **8%** breakout stop | `scanner.py` entry_setup | same p.299 rule; **10% absolute max** (p.276) | Configured proxy. |
| **−12%** intraday hard floor | `entry_exit.py` `intraday_floor = pivot × 0.88` | **"absolute maximum line in the sand of no more than 10 percent"** (p.276, p.299) | **Wider than the book's hard 10% max** — owned deviation; candidate to tighten to −10%. |
| Difficult-market tightening | market-posture overlay says "TIGHTEN" | concretely **7-8% → 5-6%**, targets 15-20% → 10-12% (p.311) | The verdict escalates but the surfaced stop/target **numbers do not move** — owned gap. |
| Position sizing | `analysis/trade_plan.py` `position_size` (0.5-1% risk) | concentration: **~25% / 4-6 names, ≤20 positions** (p.312) | Generic fixed-fractional, **not** the book's concentration model — flagged, not implemented. |

These are decision-support displays; none is a book-faithful reproduction of
Minervini's risk rules. Tracked as audit follow-ups for a possible future
"realized-stats-aware" stop module.
