# SEPA Contracts Spec — Locked As Of 2026-05-24

**Why this doc exists.** Ajay's real-money trading depends on the SEPA scoring
output (VCP, trend template, stage, RS, ADR, base count). Any refactor of the
codebase MUST preserve every contract listed here. This doc is the source of
truth for what "not broken" means. The companion regression test at
`backend/tests/test_sepa_contracts.py` asserts these contracts machine-readably.

If you change anything in this doc, you are changing trading logic. Bump the
version below and get explicit sign-off before merging.

**Version:** 1.0 (2026-05-24)
**Anchor commit:** locked at the SHA of the first commit that adds this doc.

---

## 1. The blast radius — what CAN and CANNOT change

| Module path                              | Touched by Massive options migration? | Trading-critical? |
|------------------------------------------|---------------------------------------|-------------------|
| `backend/sepa/**`                        | ❌ NO                                  | ✅ YES             |
| `backend/options/**`                     | ✅ YES — full rewrite OK               | ❌ NO (display only) |
| `backend/main.py` SEPA route handlers    | ❌ NO                                  | ✅ YES             |
| `backend/main.py` `/options/*` handlers  | ✅ YES                                 | ❌ NO              |
| `frontend/src/hooks/useSepa.ts`          | ❌ NO — type shape locked              | ✅ YES             |
| `frontend/src/pages/Sepa.tsx`            | ❌ NO                                  | ✅ YES             |
| `frontend/src/pages/SepaCandidate.tsx`   | ⚠ partial — only the Options Flow tab body   | ✅ YES (rest of page) |
| `frontend/src/components/SepaCandidate*` | ❌ NO                                  | ✅ YES             |
| `frontend/src/components/SepaSignalChips`| ❌ NO                                  | ✅ YES             |
| `frontend/src/components/Options*`       | ✅ YES                                 | ❌ NO              |
| `frontend/src/hooks/useOptionsPulse.ts`  | ✅ YES                                 | ❌ NO              |

**Rule:** If a migration PR touches any row marked "❌ NO" under "Touched by"
AND "✅ YES" under "Trading-critical", the PR description must include an
explicit "WHY THIS SEPA CHANGE" section with justification.

---

## 2. SEPA scan response — `/sepa/scan` (GET + POST)

Returns the latest scan results. Top-level shape:

```json
{
  "as_of":              "ISO 8601 string | null",
  "generated_at":       "ISO 8601 string",
  "duration_sec":       "float (informational)",
  "universe_size":      "int",
  "analyzed":           "int",
  "candidate_count":    "int",
  "retry_count":        "int",
  "recovered_count":    "int",
  "permanent_failures": "list[{symbol: str, error: str}]",
  "candidates":         "list[CandidateRow]   — is_candidate=true subset",
  "all_results":        "list[CandidateRow]   — full universe",
  "market_context":     "dict | null          — informational, may evolve"
}
```

Both `candidates` and `all_results` arrays contain `CandidateRow` objects with
the schema in §3.

**Sort:** caller-controlled at read time. Backend does NOT pre-sort.

---

## 3. SEPA `CandidateRow` — the row contract

This is the contract every SEPA card / detail page reads. ALL listed fields
MUST be present on every row, even when null. Schema mirrors what
`backend/sepa/scanner.py:_analyze_symbol()` returns on the happy path.

```python
CandidateRow = {
    # ── Identity ─────────────────────────────────────────────────────────
    "symbol":           str,                  # uppercase ticker
    "name":             str | None,           # company long name
    "last_close":       float | None,         # most recent daily close
    "day_change_pct":   float | None,         # % change vs prior close

    # ── Composite score (Minervini-weighted) ─────────────────────────────
    "score":            float,                # 0 - 100, see §4 for weights
    "rating":           str,                  # STRONG_BUY | BUY | WATCH | NEUTRAL | AVOID
    "is_candidate":     bool,                 # see §5 for gate logic

    # ── Pillars ──────────────────────────────────────────────────────────
    "trend": {                                # Minervini Trend Template
        "symbol":         str,
        "pass_all":       bool,
        "passed":         int,                # 0 - 8
        "checks":         dict[str, bool],    # 8 named gates (see §6)
        "preferred":      dict[str, bool],    # bonus check, informational
        "price":          float | None,
        "ma50":           float | None,
        "ma150":          float | None,
        "ma200":          float | None,
        "week52_high":    float | None,
        "week52_low":     float | None,
        "pct_above_low":  float | None,
        "pct_below_high": float | None,
    },
    "rs_rank":          int | None,           # 1 - 99 IBD-style percentile
    "stage": {                                # Weinstein 4-stage classifier
        "stage":         int,                 # 1 | 2 | 3 | 4
        "label":         str,                 # Basing | Advancing | Topping | Decline
        "slope_up":      bool,                # 200-DMA slope direction
        "dist_200_pct":  float,               # % distance from 200-MA
    },
    "adr_pct":          float | None,         # Average Daily Range %

    # ── Setup ────────────────────────────────────────────────────────────
    "vcp":              VCPResult | None,     # see §7
    "power_play": {
        "is_power_play":        bool,
        "best_40d_gain_pct":    float | None,
    },
    "base_count": {                           # which base #
        "base_count":     int,                # 1, 2, 3, ...
        "is_early_base":  bool,               # ≤ 2 = good
        "is_late_stage":  bool,               # ≥ 4 = penalty
    },
    "entry_setup": {                          # null when no VCP and no Power Play
        "type":   "VCP" | "POWER_PLAY",
        "pivot":  float,
        "stop":   float,
    } | None,
    "trade_plan":       TradePlan,            # always present; see TradePlan spec

    # ── Volume ───────────────────────────────────────────────────────────
    "volume": {
        "last_vol":               int | None,
        "avg_vol_50":             float | None,
        "up_down_vol_ratio":      float | None,    # ≥ 1.3 = accumulating
        "accumulation":           bool,            # legacy binary flag
        "accumulation_strength":  "strong" | "accumulating" | "neutral" | "distributing" | None,
        "accumulation_days_25":   int | None,      # count over last 25 sessions
        "distribution_days_25":   int | None,
        "cmf_20":                 float | None,    # Chaikin Money Flow
        "cmf_signal":             "inflow" | "outflow" | None,
        "pocket_pivot":           bool,
        "pocket_pivot_detail":    dict | None,
        "high_vol_breakout":      bool,
        "is_drying_up":           bool,
        "vol_dryup":              float | None,
    },

    # ── Momentum + risk ──────────────────────────────────────────────────
    "dual_momentum": {                        # Antonacci 1m/3m/6m/12m
        "return_1m":    float | None,
        "return_3m":    float | None,
        "return_6m":    float | None,
        "return_12m":   float | None,
        "abs_mom_pass": bool,
        "beats_spy":    bool | None,
        "dm_score":     float | None,
    } | None,
    "sell_signals": {
        "action":                              "HOLD" | "WATCH" | "SELL",
        "severity":                            int,
        "signals":                             list[str],
        "climax_15d_gain_pct":                 float | None,
        "largest_1d_down_pct_stage2":          float | None,
        "largest_1w_down_pct_stage2":          float | None,
        "today_1d_return_pct":                 float | None,
        "today_1w_return_pct":                 float | None,
    },

    # ── Liquidity ────────────────────────────────────────────────────────
    "liquidity": {
        "liquid":           bool,
        "avg_dollar_vol":   float,
        "avg_shares":       float,
        "reason":           str,
    },

    # ── Categorical metadata ─────────────────────────────────────────────
    "is_etf":         bool,
    "etf_data":       ETFData | None,        # see ETFData spec
    "is_pioneer":     bool,
    "pioneer_themes": list[{ "id": str, "label": str }],
}
```

**Optional but commonly-present fields** (may be added without bumping the
contract version):

- `fundamentals` — CANSLIM C+A+I checks (gated behind `with_catalyst=True`)
- `moat` — Buffett-style economic moat score
- `catalyst` — earnings catalyst summary
- `insider` — recent insider transactions
- `scanned_at` — per-row analysis timestamp (added by on-demand analyze path)

---

## 4. Score weights — LOCKED

`backend/sepa/scanner.py:60` — DO NOT CHANGE without bumping contract version
and discussing impact on Ajay's open positions.

```python
SCORE_WEIGHTS = {
    "trend_template": 30,   # 8/8 = 30, 7/8 = 26, 6/8 = 22 ...
    "rs_rank":        25,   # rs/99 * 25
    "stage_2":        10,
    "setup":          15,   # VCP or Power Play
    "fundamentals":   10,   # CANSLIM C+A+I gates
    "volume":          5,
    "liquidity_adr":   5,
}
# Sum = 100 + late-base penalty of -8 if applicable.
```

### Rating thresholds — LOCKED

`backend/sepa/scanner.py:48`

```python
def _rating_label(score: float) -> str:
    if score >= 85: return "STRONG_BUY"
    if score >= 70: return "BUY"
    if score >= 60: return "WATCH"
    if score >= 40: return "NEUTRAL"
    return "AVOID"
```

---

## 5. `is_candidate` gate — LOCKED

A row is `is_candidate: True` if and only if ALL of:

1. `trend.pass_all == True` (all 8 Trend Template gates pass)
2. `stage.stage == 2` (Weinstein Stage 2 advancing)
3. `entry_setup is not None` (VCP or Power Play present)
4. `base_count` is None OR `base_count.is_late_stage == False` (≤3 bases)
5. `liquidity.liquid == True` (institutional-grade liquidity)

Source: `backend/sepa/scanner.py:265-271`.

**Why this matters:** the /sepa list shows is_candidate=True names by default.
Changing any gate would change what shows up on Ajay's primary research view.

---

## 6. Trend Template — 8 gates LOCKED

`backend/sepa/trend_template.py:58-69`. Identifiers are exact dict keys.

```python
checks = {
    "price_above_ma150_and_ma200":   price > MA150 and price > MA200,
    "ma150_above_ma200":             MA150 > MA200,
    "ma200_trending_up":             MA200_today > MA200_22_bars_ago,
    "ma50_above_ma150_above_ma200":  MA50 > MA150 > MA200,
    "price_above_ma50":              price > MA50,
    "at_least_30pct_above_52w_low":  pct_above_low >= 30,
    "within_25pct_of_52w_high":      pct_below_high <= 25,
    "rs_rank_at_least_70":           rs_rank >= 70,    # set by scanner after rs_ranks() runs
}
preferred = {
    "ma200_trending_up_5mo":         MA200_today > MA200_110_bars_ago,
}
passed = sum(checks.values())  # 0 to 8
```

---

## 7. VCP rules — LOCKED

`backend/sepa/vcp.py`. Constants embedded inline:

| Rule                                    | Threshold                       | Line |
|-----------------------------------------|---------------------------------|------|
| Lookback window                         | 325 bars (≈65 weeks)            | 51   |
| Minimum contractions                    | 2                               | 152  |
| Maximum contractions (ideal range)      | 6                               | 148  |
| Monotonic shrinkage tolerance           | each ≤ 75% of previous          | 115  |
| Tight right side (final contraction)    | ≤ 10%                           | 117-119 |
| Maximum base depth                      | 60% (anything above = too_deep) | 66   |
| Ideal base depth range                  | 10% to 35%                      | 149  |
| Pivot quality — prior advance required  | ≥ 20% from pre-base low         | 138  |
| Volume drying-up threshold              | final_vol / avg_base_vol < 0.8  | 145  |

**`has_base = True`** requires ALL of:
- `n_contractions >= 2`
- `monotonic_shrinkage == True`
- `tight_right_side == True` (final contraction ≤ 10%)
- `too_deep == False` (base ≤ 60%)
- `pivot_quality_ok == True` (≥ 20% prior advance)

---

## 8. Weinstein Stage classifier — LOCKED

`backend/sepa/stage.py`. Decision tree:

| Stage | Condition |
|-------|-----------|
| **2** (Advancing) | `slope_up AND price > MA50 > MA150 > MA200` |
| **4** (Decline)   | `slope_down AND price < MA50 < MA150 < MA200` |
| **3** (Topping)   | `price < MA50 AND slope_up AND price > MA200 * 0.9` |
| **1** (Basing)    | Default — any non-matching state |

Slope = MA200 today vs MA200 22 bars ago. `slope_up = today > prior`.

---

## 9. Base count — LOCKED

`backend/sepa/base_count.py`:

- Lookback: 504 bars (≈2 years)
- New base counted when: new 50-day rolling high reached AFTER ≥15 bars of
  consolidation AND >30 bars since last base break
- `is_early_base = base_count <= 2`
- `is_late_stage = base_count >= 4`  ← this triggers the -8 score penalty

---

## 10. Liquidity floor + ADR — LOCKED

`backend/sepa/adr.py`:

- ADR period: 20 bars
- Liquidity gates (cookstock-style institutional floor) — exact thresholds in
  `adr.liquidity_check()`. `liquid: bool` is what the gate exposes.
- A scan with `require_liquidity=True` (default) skips non-liquid names entirely.
- The on-demand analyze path uses `require_liquidity=False` so detail pages
  work for typed-in tickers outside the universe (RYOJ, NOK, etc).

---

## 11. The Massive options migration — explicit non-impact

The $200 Massive plan upgrade only touches what's in `backend/options/**` and
`frontend/src/components/Options*` + `useOptionsPulse.ts`. The migration:

1. Removes the lazy `_massive_options_disabled` flag (no longer needed —
   the new key returns 200, not 401).
2. Removes the yfinance fallback for options chains, since Massive is now
   ~30× faster.
3. Adds new fields to the SOIR row (e.g. greeks aggregates, UOA flag).
4. Drops the 8-second poll loop in `OptionsFlowPanel.tsx` — Massive returns
   synchronously.

**Nothing in §2-§10 changes.** The regression test at
`backend/tests/test_sepa_contracts.py` is run before AND after every options
migration commit to prove nothing leaked. CI gate to be added.

---

## 12. How to extend this doc safely

### The hard rule (added 2026-05-25 after the RFC 001 lesson)

**SEPA's core formula is locked. Never change `SCORE_WEIGHTS`, the 8 trend
template gates, the VCP rules, the stage classifier, the rating tier
thresholds, or the `is_candidate` gate without explicit user sign-off
*before* any code is written.**

This rule exists because Ajay traded real positions against the v1.0
SEPA formula in early 2026 and any silent drift in the math directly
affects his live decisions. The trade-off "we'll backtest and revert if
bad" is unacceptable because the backtest fires AFTER candidate ratings
have already shifted on a live deploy.

**Operational consequence**: any agent or contributor who's tempted to
"upgrade" SEPA — even with a backtest showing the new weights are
"better" — must instead build a **SEPA v2 page** (separate route,
separate score table, separate UI) where the new formula runs in
parallel without affecting the v1 list. The user evaluates v2 over
weeks/months of live observation, then decides whether to promote v2
to default — never the other way around.

### What's safe to change (no RFC required)

* **Data source swaps**: e.g. yfinance → Massive for the same input fields.
  The output values must agree within rounding tolerance, validated by
  the same regression test. Example: 2026-05-24 CANSLIM swap from
  yfinance to Massive financials (`backend/sepa/canslim.py`). Same
  `passed: X/3` output, same component weight, just faster + more
  reliable input.
* **Adding optional new fields** to `CandidateRow` that the formula
  doesn't read. Frontend can surface them as chips, but the SCORE
  calculation must not change.
* **UI/display changes** (chip styling, tooltips, drill-in modals) —
  pure presentation, no scoring impact.

### What requires explicit sign-off + SEPA v2 path

* Changing `SCORE_WEIGHTS` values
* Changing rating tier thresholds (85/70/60/40)
* Changing the `is_candidate` gate logic
* Adding a new score component (even at small weight)
* Changing VCP detection thresholds (contraction count, depth, pivot quality)
* Changing trend template (adding a 9th gate, modifying the 8 existing)
* Changing the Stage classifier decision tree
* Changing the base count rules

For any item in the second list, the workflow is:

1. **Propose**: agent writes RFC in `docs/rfcs/NNN-*.md` describing the
   change, but explicitly recommends building it as a SEPA v2 page first.
2. **Confirm scope**: user confirms whether to (a) implement on SEPA v2
   only, (b) reject entirely, or (c) [rare] promote directly to v1 with
   full backtest + version bump.
3. **Build SEPA v2 page**: new route (e.g. `/sepa-v2`), new score
   computation in `backend/sepa/scanner_v2.py` (or behind a flag), new
   regression test snapshot. v1 SEPA stays untouched.
4. **Live observe**: user runs both side-by-side for N weeks.
5. **Decide**: only after observation does the user authorize promoting
   v2 to v1.

Adding a NEW optional field (e.g. new categorical metadata) does NOT require
the RFC — it's additive and won't break existing readers. Just document it
in §3 under "Optional but commonly-present fields".

Removing or renaming a field IS a breaking change. RFC required.
