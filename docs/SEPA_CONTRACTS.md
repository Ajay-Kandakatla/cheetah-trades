# SEPA Contracts Spec — Locked As Of 2026-05-24

**Why this doc exists.** Ajay's real-money trading depends on the SEPA scoring
output (VCP, trend template, stage, RS, ADR, base count). Any refactor of the
codebase MUST preserve every contract listed here. This doc is the source of
truth for what "not broken" means. The companion regression test at
`backend/tests/test_sepa_contracts.py` asserts these contracts machine-readably.

If you change anything in this doc, you are changing trading logic. Bump the
version below and get explicit sign-off before merging.

**Version:** 1.1 (2026-05-31) — added §5b `is_buyable` volume-confirmed-breakout
pillar (book p.203) + §4 institutional-sponsorship rank demotion (book p.195).
Prior: 1.0 (2026-05-24).
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
        "cmf_signal":             "inflow" | "outflow" | "neutral" | None,
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
- `qualifier` — bool, added 2026-05-27. True when `trend.pass_all AND
  liquidity.liquid`. Matches Minervini's "Trend Template is a qualifier"
  semantics (book p. 79). The wider WATCHLIST tier; `is_candidate` remains
  the strict BUYABLE-NOW tier. Always: `is_candidate=True ⇒ qualifier=True`.
  Surfaced in the top-level scan response as `qualifier_count` and rendered
  in the SEPA hero stat strip alongside `candidate_count`. Additive; does
  not change `is_candidate` semantics or any scoring weight.

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
    "fundamentals":   10,   # earnings quality — see note below
    "volume":          5,
    "liquidity_adr":   5,
}
# Sum = 100 + late-base penalty of -8 if applicable.
```

> **The `fundamentals` bucket = earnings quality (Minervini Ch.8, book p.140-159)**
> *(meaning changed 2026-06-08, weight unchanged at 10).* It used to be just the
> CANSLIM C+A+I count /3. It is now scaled by the **0-100
> `sepa/earnings_quality.py` score**, which *subsumes* C+A+I and adds the Code 33
> (EPS+sales+margin triple-acceleration, p.158-159), margin expansion (p.145-147),
> EPS/sales acceleration (p.140), and a sales-driven quality penalty for
> cost-cutting/one-time beats (p.141-144). `bonus = 10 × eq_score/100`. When eq is
> unscored (thin history / yfinance fallback) it falls back to the legacy
> `passed/3` bonus, so the prior signal is never lost. Full derivation +
> page cites: `docs/sepa/earnings_quality_methodology.md`. Thresholds locked by
> `test_sepa_contracts.test_earnings_quality_thresholds_locked`.

**Post-sum penalties** (applied to `score` AFTER the weighted sum, so the
weights above stay summed to 100):

| Penalty | Amount | Source |
|---|---|---|
| Late-stage base | −8 | exhaustion (≥4 bases) |
| Institutional-sponsorship demotion | −0 / −4 / −10 / −18 by avg daily $-vol tier | **book p.195** (added 2026-05-31) |
| Earnings-quality red flag | −4 (low-quality beat / inventory) · −6 (double trouble) | **book p.143, 155-157** (Ch.8, added 2026-06-08) |

> **Sponsorship tiers** (`scanner.SPONSORSHIP_TIERS`, locked by
> `test_sponsorship_penalty_tiers_locked`): ≥$100M → 0; $20M–$100M → −4;
> $5M–$20M → −10; <$5M → −18; unknown → 0. Book p.195: *"limit your selections
> to those displaying evidence of being supported by institutional buying."*
> The book gives the concept but **no $ number and no nominal share-price floor**
> (its "Cheap Trap", p.43, is about valuation, not share price). Bands are the
> user-approved (2026-05-31) codification — "tiered bands, stay book-pure, no
> price floor." This sinks thin single-digit names (CVGI ≈ $2.3M/day → −18)
> below liquid leaders without excluding them.

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

## 5. `is_candidate` (watchlist) + `is_buyable` (entry-now) gates — LOCKED

Two distinct tiers (book p.79 separates the *qualifier* from the *buy point*):

### 5a. `is_candidate` = the qualifier / watchlist (book p.79)

A row is `is_candidate: True` if and only if BOTH of:

1. `trend.pass_all == True` (all 8 Trend Template gates pass)
2. `liquidity.liquid == True` (institutional-grade liquidity)

> Book p.79: *"The Trend Template is a qualifier."* A "candidate" is a name worth
> **considering**, not necessarily buying today. (Fixed 2026-05-28 — `is_candidate`
> used to carry the strict gate below; that contradicted the book.)

### 5b. `is_buyable` = the strict "buy NOW" gate (book pp.79-83, 195, 198-204)

A row is `is_buyable: True` if and only if ALL of:

1. `trend.pass_all == True`
2. `stage.stage == 2` (Weinstein Stage 2 advancing)
3. `entry_setup is not None` (VCP or Power Play present)
4. `base_count` is None OR `base_count.is_late_stage == False` (≤3 bases)
5. `liquidity.liquid == True`
6. **`volume.high_vol_breakout OR volume.pocket_pivot`** — a VOLUME-CONFIRMED
   breakout (**added 2026-05-31**).

> Book p.203 verbatim: *"the point at which you want to buy is when the stock
> moves above the pivot point **on expanding volume**."* A breakout on
> below-average volume is NOT a Minervini buy (p.203-204: *"almost every failed
> base structure can be traced back to some faulty characteristic that was
> overlooked"*). This drops CVGI-class single-digit names that pass 8/8 but are
> breaking out on thin volume from the buyable tier — they stay `is_candidate`.

Source: `backend/sepa/scanner.py` (`_analyze_symbol` full + fast paths).
Contract test: `test_is_candidate_gate_logic` + `test_is_buyable_gate_logic`.

**Why this matters:** the /sepa list ranks by `score` and the buyable tier flags
what's actionable today. Both feed Ajay's real-money decisions.

### 5c. `setup_ready` + breakout recency — the toggleable "Enter" (2026-06-02)

`is_buyable` is the canonical STRICT gate (today's volume-confirmed breakout) and
is unchanged. Two additive fields let the FE relax the SAME-DAY breakout
requirement without touching the strict gate (user: *"it's ok to not have high
volume breakout… they may have a breakout in the past week sometime"*):

- **`setup_ready`** (row, `scanner._is_setup_ready`) = is_buyable gates **1–5
  minus** the volume-breakout clause (#6). The "in a proper base, waiting for the
  trigger" tier. `is_buyable == setup_ready AND (high_vol_breakout OR pocket_pivot)`.
- **`volume.days_since_breakout`** (int | null) = bars since the most recent
  volume-confirmed breakout within `BREAKOUT_RECENCY_LOOKBACK` (**15**); `0` =
  today, `null` = none in window. A bar is a breakout when its volume > 1.5× the
  trailing 50-day average AND its close exceeds the prior-21-bar high (the same
  test as `high_vol_breakout`, vectorized). At the last bar it equals
  `high_vol_breakout`.

The FE **Breakout** toggle maps to:

| Mode | Enter set |
|---|---|
| **Today** (default, book-strict) | `is_buyable` |
| **≤1wk** | `setup_ready AND days_since_breakout ≤ 5` |
| **Any** | `setup_ready` (no trigger gate) |

The 15-bar horizon and the ≤5 "1-week" threshold are pragmatic recency
operationalizations, **not** verbatim book numbers — Minervini's canonical buy
point is the breakout day itself (p.203). Contract: `test_breakout_window.py`
(`make contracts-breakout`) + `test_setup_ready_is_buyable_minus_breakout`.

> **Data-integrity dependency — the phantom-bar guard (2026-06-02).** Gate #6
> reads the LAST cached daily bar. Before the regular session prints, the bulk
> snapshot can echo the prior day's completed aggregate into a bar stamped with
> *today's* date — two adjacent bars with byte-identical close AND volume. The
> duplicate close already sits inside `recent_high`, so `last_close > recent_high`
> (the breakout test in `volume.analyze`) becomes mathematically impossible:
> `high_vol_breakout` reads `False` for the **entire universe** and `is_buyable`
> collapses to ~0. This silently masks every real breakout. Guarded two ways in
> `backend/sepa/prices.py`: `patch_latest_closes` refuses to append a snapshot bar
> that duplicates the prior stored session, and `load_prices` strips a trailing
> exact-duplicate bar at read time (`_drop_phantom_tail`) so the cache self-heals
> on the next scan. Regression: `backend/tests/test_phantom_bar.py`
> (`test_phantom_suppresses_breakout_guard_restores_it`), run via
> `make contracts-phantom`. Two real sessions never share volume to the share, so
> the guard only ever drops placeholders.

> **Staleness floor — delisted / halted / renamed (2026-06-02).** `_analyze_symbol`
> (and the fast path) drop any symbol whose newest bar is older than
> `prices.STALE_MAX_CALENDAR_DAYS` (**14** ≈ 10 trading days) BEFORE scoring. A
> delisted name keeps a frozen last bar in the cache (the patcher bumps its TTL
> but appends nothing because the feed returns NotFound), and that frozen bar can
> read as a pocket pivot / breakout and leak straight into the buyable tier — e.g.
> **CFLT** stopped trading 2026-03-16 on an M&A volume spike yet scored
> `is_buyable` ~3 months later with a dead chart. The gap between an active name
> (last bar 0–3 days old) and a delisted one (months) is large, so 14 days clears
> weekend / holiday / transient-patch-gap noise. `prices.is_stale(df, asof=…)`;
> regression in `test_phantom_bar.py` (`test_is_stale_*`).

### 5d. The green **ENTER** verdict requires Stage 2 (2026-06-02)

The per-card **decision verdict** (`entry_exit.decision` — the green/amber banner
"In the buy zone … Enter with a close-basis stop") and the **pivot meter**
(`frontend/src/lib/pivotTiming.ts`, the `GO · at pivot on volume` pill) are
SEPARATE code paths from `is_buyable`. Before this fix `entry_exit._decide`
consulted stage **only to reject Stage 3/4** — so a **Stage 1 base** that fired a
one-day pocket-pivot/volume pop with price sitting at the pivot read
`actionable + volume-confirmed → ENTER`, **contradicting the same card's WATCH
verdict and `S1 · Basing` label** (the **SMCI** case, 2026-06-02).

> **Book — only buy Stage 2.** Stage 1 is the neglect/basing phase (p.69); the buy
> comes on the **Stage 1→2 transition** confirmed by the Trend Template (p.79) and
> a breakout on expanding volume (p.203). A volume pop *inside* a Stage 1 base is
> exactly the false-start the template filters out.

**Contract:** `ENTER` (green) may fire only when the name is book buyable-eligible:

- Backend `entry_exit.build_entry_exit` takes `setup_ready` (the scanner's
  `_is_setup_ready`: Trend Template 8/8 + Stage 2 + setup + not late + liquid) and
  `_decide` gates the ENTER branch on it; standalone (no `setup_ready` passed) it
  falls back to `stage == 2`. A non-eligible in-zone name returns **WAIT** ("still
  basing (Stage 1) — not a confirmed Stage 2 advance") / **HOLD_WATCH**, never ENTER.
- Frontend `pivotTiming` mirrors the gate: an at/above-pivot name that is not
  `is_buyable`/`setup_ready` (or, fallback, `stage.stage === 2`) downgrades from
  `GO`/`AT_PIVOT` to the new **`NOT_STAGE2`** state ("Wait · not Stage 2 yet")
  instead of flashing a green GO.

This keeps the banner + meter in lock-step with `is_buyable` and the Stage label —
no more WATCH-but-ENTER cards. Contracts: `test_entry_decision_stage2.py` +
`test_enter_verdict_requires_stage2` (in `test_sepa_contracts.py`) +
`pivot-meter` frontend contract (`scripts/contracts.mjs`). Methodology:
`docs/sepa/entry_decision_methodology.md`.

---

## 6. Trend Template — 8 gates LOCKED

**Source of truth:** Mark Minervini, *Trade Like a Stock Market Wizard* (McGraw-Hill, 2013),
**book p. 79** — the "Trend Template" box listing the 8 criteria. Verified verbatim against
the printed list 2026-05-27.

> Quote from book p. 79 (verbatim): *"It's important to point out that a stock must
> meet all eight of the Trend Template criteria to be considered in a confirmed
> stage 2 uptrend."*
>
> Note also book p. 79 prelude: *"The Trend Template is a qualifier."* — i.e., this
> set of 8 criteria yields the screened universe Minervini then runs fundamentals +
> setup analysis against. It is NOT his definition of "ready to buy."

Code location: `backend/sepa/trend_template.py:58-69`. Identifiers are exact dict keys.

| # | Book p.79 criterion | Code expression |
|---|---|---|
| 1 | Stock price above both 150-day (30-week) AND 200-day (40-week) MA | `price > MA150 and price > MA200` |
| 2 | 150-day MA above 200-day MA | `MA150 > MA200` |
| 3 | 200-day MA trending up **at least 1 month** (preferably 4–5 months) | `MA200_today > MA200_22_bars_ago` (22 bars = 1 mo) |
| 4 | 50-day (10-week) MA above both 150-day and 200-day | `MA50 > MA150 > MA200` |
| 5 | Stock price above 50-day MA | `price > MA50` |
| 6 | Stock price **at least 30% above** 52-week low | `pct_above_low >= 30` |
| 7 | Stock price **within 25% of** 52-week high | `pct_below_high <= 25` |
| 8 | RS rank (IBD) **≥ 70** (preferably 80s–90s) | `rs_rank >= 70` |

Preferred (book p.79, criterion 3 parenthetical "preferably 4–5 months minimum"):
- `ma200_trending_up_5mo`: `MA200_today > MA200_110_bars_ago` (110 bars ≈ 5 mo)

```python
passed = sum(checks.values())  # 0 to 8
```

---

## 7. VCP rules — LOCKED

**Source of truth:** Mark Minervini, *Trade Like a Stock Market Wizard*,
**Chapter 10 "A Picture Is Worth a Million Dollars," pp. 198–203.** Verified
2026-05-27.

> **Book p. 198 (definition):** *"A common characteristic of virtually all
> constructive price structures (those under accumulation) is a contraction
> of volatility accompanied by specific areas in the base structure where
> volume contracts significantly."*
>
> **Book p. 198 (contraction count):** *"During a VCP, you will generally see
> a succession of anywhere from **two to six contractions**... Typically,
> most VCP setups will be formed by two to four contractions, although
> sometimes there can be as many as five or six."*
>
> **Book p. 199 (shrinkage rule):** *"I like to see each successive
> contraction contained to **about half (plus or minus a reasonable amount)**
> of the previous pullback or contraction."*
>
> **Book p. 200 (base width):** *"that is **four to seven weeks** in duration"*
> (Darvas-style flat base). Bases can range 3–60 weeks per p. 197.
>
> **Book p. 186 (max correction):** *"the correction for a healthy stock from
> peak to low will be contained within **25 to 35 percent** and during severe
> bear market declines could be as much as **50 percent**, but the less, the
> better. A correction of more than 50 percent is generally too much."*
>
> **Book p. 202 (worked example — VIVO "40W 31/3 4T"):** 40-week base,
> 31% deepest correction, 3% final pullback, 4 contractions.
> Earlier in the same example (p. 201–202): 31% → 17% → 8% → 3% sequence.
>
> **Book p. 203 (volume):** *"Tightness in price... should be accompanied
> by a significant decrease in trading volume."* Buy point: *"when the stock
> moves above the pivot point on expanding volume."*

Code location: `backend/sepa/vcp.py`. Contracts: `backend/tests/test_vcp.py`
(behavioral, synthetic series) + `tests/test_sepa_contracts.py::test_vcp_constants_locked`
(source guard). Full spec: **`docs/sepa/vcp_methodology.md`**.

> **Downstream consumer — Demand Zones (2026-06-07).** `backend/supply_demand/
> demand_zones.py` reads `base_low`, `pivot_buy_price`, and `base_depth_pct` off
> `vcp.detect` to build the `/demand-zones` price bands. Renaming or dropping any
> of those three fields breaks the demand-zone band — guarded by
> `tests/test_supply_demand.py::test_zone_source_is_the_locked_vcp_detector` and
> the base→zone mapping tests. Spec: `docs/supply_demand/demand_zones_methodology.md`.

> **Base-window rewrite (2026-06-01).** The detector now measures the base on
> the **most recent CONTRACTING consolidation**, not high-to-low across the
> whole 325-bar window. Book p.205: *"the contractions will be smaller from left
> to right as supply is absorbed."* The old whole-window measure read every
> momentum leader as 60–94% deep → `too_deep` → **zero VCPs** (see "Resolved
> gaps" below).

| Rule | Book source | Threshold in code (current) |
|---|---|---|
| Search horizon (max base age) | p.197 "3 to as many as 60 weeks" | 325 bars (≈65 wks) — SEARCH window, not the base |
| Recent-base isolation | p.205 "smaller from left to right" | maximal suffix of contractions with decreasing depth |
| Min / max contractions | p.198–199 "two to six" | 2 ≤ n ≤ 6 |
| End-to-end tightening | p.199 "about half ± reasonable amount" | final ≤ 0.6 × first contraction |
| Tight right side (final contraction) | p.202 example "3 percent" | ≤ 12% |
| Maximum base depth | p.186 ">50% generally too much" | base ≤ 40% (else `too_deep`) |
| Minimum base depth | p.198 "say, 25 percent" / handle ~5% | base ≥ 5% (sub-handle = flat line) |
| Ideal base depth (flag) | p.186 "25 to 35 percent" | 8%–35% (`ideal_depth_range`) |
| Pivot quality — prior advance | p.197 "forms after an advance" | ≥ 20% from pre-base low to base high |
| Volume drying (flag) | p.205 "volume contracts" | final_vol / base_vol < 0.8 |

**`has_base = True`** requires ALL of (code, vcp.py current logic):
- `n_contractions >= 2`
- end-to-end tightening — `final ≤ 0.6 × first` contraction depth
- `base_depth_pct >= 5` (deep enough to be a real pullback)
- `too_deep == False` (base ≤ 40%)
- `tight_right_side == True` (final contraction ≤ 12%)
- `pivot_quality_ok == True` (≥ 20% prior advance)

**Resolved gaps** (2026-05-27 audit → fixed 2026-06-01, locked by `test_vcp.py`):
1. ✅ Whole-window depth → now isolates the most recent contracting base
   (`test_measures_recent_base_not_full_window`).
4. ✅ `pivot_quality` now measures the pre-base low up to the base's left-side
   high, not an unrelated window low.

**Open** (acceptable): the 5-bar swing window is tight, so weekly-scale Ts in
very long bases may be missed; first-contraction magnitude is captured by the
overall depth gate rather than a separate "≈25%" rule.

---

## 8. Weinstein Stage classifier — LOCKED

**Source of truth:** Minervini Ch 5 "Trading with the Trend," **pp. 65–77**.
Stan Weinstein 4-stage framework as adopted by Minervini (book p. 64-65 cites
Weinstein's *Secrets for Profiting in Bull and Bear Markets*, 1988).

> **Book p. 66 (four stages):**
> 1. Stage 1 — Neglect phase: consolidation
> 2. Stage 2 — Advancing phase: accumulation
> 3. Stage 3 — Topping phase: distribution
> 4. Stage 4 — Declining phase: capitulation
>
> **Book p. 69 (Transition Stage 1→2, "Transition Criteria"):**
> 1. Stock price above both 150-day and 200-day MA.
> 2. 150-day MA above 200-day MA.
> 3. 200-day MA has turned up.
> 4. Series of higher highs and higher lows.
> 5. Large up weeks on volume spikes vs low-volume pullbacks.
> 6. More up weeks on volume than down weeks on volume.
>
> **Book p. 71–72 (Stage 2 characteristics):** price above 200-day, 200-day
> in uptrend, 150-day above 200-day, 50-day above 150-day, volume spikes
> on up days/weeks vs contractions on pullbacks.
>
> **Book p. 74–76 (Stage 3 characteristics):** widening volatility, major
> price break on volume since stage 2 start, may undercut 200-day, 200-day
> losing upward momentum and flattening.
>
> **Book p. 75 (Stage 4 characteristics):** vast majority of price action
> below 200-day, 200-day in definite downtrend, near/at 52-week lows,
> lower lows and lower highs, short MAs below long MAs.

Code location: `backend/sepa/stage.py`. Decision tree:

| Stage | Condition | Book reference |
|-------|-----------|----------------|
| **2** (Advancing) | `slope_up AND price > MA50 > MA150 > MA200` **AND** volume confirms (not distributing, no CMF outflow) | p. 71-72 (geometry **and volume**) |
| **3** (Topping — geometry) | `price < MA50 AND price > MA200 * 0.9 AND MA150 > MA200` (slope-agnostic) | p. 74 (200-day "loses upside momentum, flattens, rolls over"; price "may undercut its 200-day") |
| **3** (Topping — volume override) | Geometry says Stage 2 BUT `vol.accumulation_strength == 'distributing'` OR `vol.cmf_signal == 'outflow'` | p. 74-76 (distribution is a stage-3 tell) |
| **4** (Decline)   | `slope_down AND price < MA50 < MA150 < MA200` | p. 75 |
| **1** (Basing)    | Default — any non-matching state | p. 67 |

Slope = MA200 today vs MA200 22 bars ago. `slope_up = today > prior`.
22 bars ≈ 1 month, matching book p. 79 trend template criterion #3.

**Stage-3 slope fix (2026-06-09, book-audit, explicit user sign-off).** The
geometric Stage-3 branch previously required a *rising* 200-day MA
(`slope_up`). That is backwards for a top: **book p.74** — *"The 200-day moving
average will lose upside momentum, flatten out, and then roll over into a
downtrend"* and price *"may undercut its 200-day."* So a genuinely topping name
whose 200-day had flattened/rolled over matched neither this branch nor Stage 4
(which needs a fully-inverted stack) and fell through to **Stage 1 "Basing,"**
masking the top. The branch is now **slope-agnostic** and instead requires the
prior Stage-2 stack to still be intact (`MA150 > MA200`) — the structural marker
that separates a *post-advance top* from a *post-decline base* (where the stack
is recovering from inversion, `MA150 ≤ MA200`). The earlier cite "lost MA50 but
still above MA200" was also corrected: **p.74 describes the 200-day rolling
over and price undercutting it, and does not mention the 50-day MA.**

> **Buy-side-safe by construction.** This branch can only return Stage 3, never
> Stage 2, so it cannot manufacture a buy signal (`is_buyable` and the ENTER
> verdict both require `stage == 2`). It only refines the Basing-vs-Topping label
> feeding the holding / sell-side read — and Topping is the more cautious,
> book-correct label for a stalling post-advance name. Quantified against the
> latest scan the day it shipped: **1 of 105 names (VRTX) moved Basing→Topping;
> 0 names moved into Stage 2.** Behavioral + regression locks:
> `backend/tests/test_stage_classifier.py`
> (`test_stage3_flat_200_rollover_is_topping_not_basing`,
> `test_stage3_branch_never_returns_stage2`). Bumping the contracts version is
> not required (the formula is now MORE faithful to the book — the original was a
> documented gap), matching the precedent of the 2026-05-28 volume-confirmation
> refinement below.

**Volume confirmation rule (added 2026-05-28, with explicit user sign-off).**
Pre-fix behaviour: classify only inspected MA geometry + 200-DMA slope.
A name with perfect Stage 2 MA stack but actively-distributing volume
was returned as `stage: 2`, directly contradicting book p.71-72 verbatim:

> *"Volume spikes on big up days and big up weeks are contrasted by
> volume contractions during normal price pullbacks. There are more up
> days and up weeks on above-average volume than down days and down
> weeks on above-average volume."*

That description IS Stage 2; its absence rules it OUT. Post-fix, when
`stage.classify(df, vol=...)` is called with the output of
`volume.analyze(df)`, a Stage-2-by-geometry result is downgraded to
Stage 3 (Topping) when **either** of the following volume signals fires:

- `vol.accumulation_strength == 'distributing'` — more selling pressure
  than buying over the recent window
- `vol.cmf_signal == 'outflow'` — Chaikin Money Flow signals
  institutional money exiting

> **How `accumulation_strength == 'distributing'` is decided** is its own
> locked spec: **`docs/sepa/distribution_methodology.md`** (v1.0, 2026-05-31).
> Short version: distribution is **volume-primary** (up/down vol ratio + CMF),
> not a distribution-day count — the count is only a `ratio < 1` gated
> backstop. Enforced by the `test_distribution_*` cases in
> `test_sepa_contracts.py`.

Downgrade payloads include two extra keys (`volume_disagreement: True`,
`volume_reason: <human-readable explanation citing the book pages>`)
so a downstream caller can surface WHY a name was reclassified.

**Backwards-compat.** `stage.classify(df)` with no `vol=` kwarg behaves
exactly as before — pure geometry. The contracts regression suite
(`backend/tests/test_sepa_contracts.py`) continues to pass against the
no-vol code path. `backend/sepa/scanner.py` was updated to compute
`vol = volume.analyze(df)` BEFORE calling `stage.classify(df, vol=vol)`
in both the full-scan and fast-scan paths.

**Why this is a contracts §12 change** despite being a refinement, not a
rewrite: it changes the **set of names returned with `stage: 2`** in
the SEPA scan output. Names previously labelled Stage 2 with distributing
volume (e.g. ANTX on 2026-05-28) now return Stage 3. Strict
`is_candidate` gate (§5) requires Stage 2, so those names also drop out
of the candidate list. Bumping contracts version not required (formula
is now MORE faithful to the book — the original was a documented gap),
but explicit user sign-off was obtained before edit.

---

## 9. Base count — LOCKED

**Source of truth:** Minervini Ch 5, **pp. 80–83** ("Where Are We on This
Mountain? The Base Count").

> **Book p. 80–81:** *"After a run upward, there is profit taking, causing
> a temporary pullback, during which the stock builds a base."* Multiple
> bases stack along a Stage 2 advance.
>
> **Book p. 81 (late-stage rule):** *"Generally, this occurs after three to
> five bases have formed along the stage 2 uptrend. The later-stage bases
> coincide with the point at which the stock's accumulation phase has
> become too obvious."*
>
> **Book p. 81 (early-base bias):** *"Bases 1 and 2 generally come off a
> market correction, which is the best time for jumping on board a new
> trend. As the stock makes a series of bases along the stage 2 uptrend,
> base 3 is a little more obvious but usually still tradable. By the time
> a fourth or fifth base occurs (if it gets that far), the trend is becoming
> extremely obvious and is definitely in its late stages."*

Code location: `backend/sepa/base_count.py`:

- Lookback: 504 bars (≈2 years) — practical horizon for a complete Stage 2 run
- New base counted when: new 50-day rolling high reached AFTER ≥15 bars of
  consolidation (≈3 weeks, matching book minimum base duration) AND >30 bars
  since last base break
- `is_early_base = base_count <= 2` ← book p. 81 "Bases 1 and 2"
- `is_late_stage = base_count >= 4` ← book p. 81 "a fourth or fifth base...
  definitely in its late stages." Triggers -8 score penalty in scanner.

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

## 11b. Derived scanners — Pullback to MA (2026-06-05)

A **derived scanner** reads the latest persisted scan and recomputes a view
from cached bars — it does **not** touch `scanner.py` or the money-path scan.
`dual_momentum.py` was the first; **`pullback_ma.py`** is the second.

- **What:** Stage-2 leaders making a brief, low-volume pullback toward the
  rising 50-day MA (Minervini "tennis ball" re-entry). **Universe: S&P 500
  only** (`UNIVERSE_MODE="sp500"`) — the broad daily scan filtered to index
  members.
- **Gate (book p.79 structural subset):** `last_close > ma50 AND ma50 > ma150
  > ma200 AND last_close > ma200`, then within `+PULLBACK_ZONE_CEILING%` of the
  50-day and retraced `≥ MIN_PULLBACK_PCT` from the 25-day recent high. It is
  intentionally **looser** than `is_candidate` (no RS≥70 / 30%-above-low hard
  gate) so the page surfaces a wider watch tier; full-SEPA names get a `SEPA`
  flag.
- **Columns:** Pullback % (retrace from 25-day high), % from MA50, RS 3M
  (`dual_momentum.return_3m`), Vol Ratio (today ÷ 20-day avg vol; `< 1.0×` =
  contracting, book p.72).
- **Configured constants (LOCKED by `test_pullback_ma_constants_locked`):**
  bands tight `<5` / mid `5–8` / deep `>8`; `VOL_AVG_LOOKBACK=20`;
  `RECENT_HIGH_LOOKBACK=25`; `PULLBACK_ZONE_CEILING=8.0`; `VOL_HEALTHY_MAX=1.0`;
  `UNIVERSE_MODE="sp500"`.
  These are operationalized from the user spec (2026-06-05), **not** invented
  Minervini precision — see `docs/sepa/pullback_ma_methodology.md`.
- **Cron + serve:** `sepa.cli pullback-scan` (weekdays 4:50pm ET, after the
  4:30 fast-scan) writes `latest_pullback.json` to the shared `cheetah-scans`
  volume; `GET /sepa/pullback-ma` serves it, falling back to live `compute()`.
- **Feature:** catalog id `pullback-ma` (`access/store.py`, `CATALOG_VERSION=4`).
- **Contracts:** `backend/tests/test_pullback_ma.py` (behavioral) +
  `test_sepa_contracts.py::test_pullback_ma_constants_locked` /
  `::test_pullback_ma_gate_is_book_structural_subset`.

**Rule for future derived scanners:** if you reuse the scan but recompute a
view, build a sibling module (like these two), keep `scanner.py` untouched,
lock any thresholds with a source-guard, and ship a methodology doc.

---

## 11c. Market Gauge (2026-06-05; Economic block wired to FRED 2026-06-06)

OUR OWN general-market health read — **not** a clone of any paid indicator
(those formulas are undisclosed; we will not reverse-engineer a real-money
signal). Educational, not advice.

- **Output:** 0–100 score + Constructive / Caution / Risk-Off + a Minervini
  exposure band. Renders on `/market-gauge` AND as a top-right nav badge on
  **every** page (`MarketGaugeBadge`).
- **13 pillars (weights sum 100, 6 categories):** Quant = index trend in-gear
  (p.79) 15 + VIX 8 · Trend-tech = distribution 6 + follow-through 4 (p.248) ·
  Breadth 6 · Flow & Liquidity = net $-vol + CMF aggregate 8 · Sentiment =
  options put/call SOIR 6 · Alt-data = insider cluster-buy breadth 4 · **Economic
  (FRED) = yield curve `T10Y3M` 8 + CPI YoY `CPIAUCSL` 9 + unemployment `UNRATE`
  9 + Fed-funds `FEDFUNDS` 8 = 34** · Macro = regime + news 9. All REAL data or
  honestly neutral.
- **Economic block is HEAVY (34/100 — Ajay 2026-06-06):** the macro block now
  outweighs the price-trend block. The 9 non-economic pillars were trimmed
  proportionally (×66/89) to keep the sum at 100; the old weights live in git.
- **Economic data is REAL, from FRED** (free key): `backend/sepa/fred.py` reads
  the four series above, cited by series id, cached in-process 24 h. Key is the
  `FRED_API_KEY` env var (in `backend/.env`, never hardcoded). No key → the four
  pillars degrade to neutral (`"n/a — set FRED_API_KEY"`), never faked. The
  yfinance `^TNX`/`^IRX` proxy (and its ×10/NaN hack) was **replaced** by FRED
  `T10Y3M`.
- **NOT wired (flagged in `config.not_wired`, never faked):** true order-flow /
  dark-pool tape, fear/greed index. (CPI / jobs / Fed-funds / FRED yield are now
  WIRED — no longer in `not_wired`.)
- **Exposure bands** restate Minervini pp.304–305 (scale down in weak tapes,
  pyramid up when in gear, pace re-entry) — educational, NOT advice.
- **Configured (NOT book-cited):** the O'Neil-style distribution/FTD numbers
  (`DIST_TOPPING=5`, `FTD_UP_PCT=1.4`, windows) — we don't hold *How to Make
  Money in Stocks* — AND the FRED economic thresholds (Fed ~2% target, Sahm-rule
  rising unemployment, tightening-vs-easing, curve inversion): the FRED *data* is
  authoritative, the macro *interpretation* is standard-macro, not book-derived.
  All locked by `test_market_gauge_locked`.
- **Code:** `sepa/market_gauge.py` (`compute()` / `get_gauge()`, 5-min cache) +
  `sepa/fred.py` (FRED reader, 24 h cache); `GET /market/gauge`. `scanner.py` and
  the daily scan untouched (Rule #2); no new cron.
- **Contracts:** `backend/tests/test_market_gauge.py` (behavioral, incl. FRED
  pillars + graceful degradation) + `test_sepa_contracts.py::test_market_gauge_locked`.

---

## 11d. Cross Junctions (2026-06-06)

Confluence screen on the Leaderboard — names that are SIMULTANEOUSLY:
1. a **SEPA candidate** (`is_candidate`, trend template + liquidity, p.79),
2. **consistently ranked** (leaderboard `persistence_pct ≥ 50` over `≥ 4` of the
   14-day window's days), and
3. a **Pullback-to-MA** candidate (`pullback_ma._evaluate_row`).

**Universe order (Ajay 2026-06-06):** S&P 500 first; if the S&P set is `< 6`,
broaden the pullback leg to the Russell 1000. Each row tags its `junction_universe`.

- **Junction score** = `0.45·SEPA + 0.30·pullback + 0.25·persistence` (configured,
  locked by `test_cross_junctions_locked`). Sortable by any leg on the FE.
- Returns **full candidate rows** so `SepaCandidateCard` keeps every chip
  (BUY/STRONG_BUY, conviction, whales, volume, VCP tightness…).
- **Code:** `sepa/cross_junctions.py` (`compute` / `get_cross_junctions`, 5-min
  cache); `GET /sepa/cross-junctions`. Derived from the scan + the rank
  leaderboard; `scanner.py` and the daily scan untouched (Rule #2).
- **Contracts:** `backend/tests/test_cross_junctions.py` +
  `test_sepa_contracts.py::test_cross_junctions_locked`.
- **Empty is valid:** when no consistently-ranked leader is currently pulling back
  (extended/cautious tape → leaders are stretched above their MAs), the section is
  empty by design — not a bug.

---

## 11e. Weekly Gauge + next-day outlook + pre-open cron (2026-06-06)

Multi-horizon companion to the daily Market Gauge (§11c). **Reads the regime
across timeframes; does NOT forecast price.**

- **Weekly gauge** (`market_gauge.compute_weekly()`): the SAME Minervini concepts
  on **weekly bars** (SPY/QQQ resampled `W-FRI`). 5 weekly pillars, **weights sum
  100** (separate `config.weekly_weights`): weekly Trend Template 45, weekly
  distribution 20, weekly momentum 15, weekly follow-through 10, macro 10.
- **Weekly MAs are book-grounded, not configured:** Minervini **p.79** gives the
  weekly equivalents in parentheses verbatim — 50-day **(10-wk)**, 150-day
  **(30-wk)**, 200-day **(40-wk)**. The weekly *lookbacks/magnitudes* (8-wk
  distribution window, 4-wk topping, +2.5% weekly FTD, ±8% momentum) ARE configured.
- **Next-day outlook** (`_outlook()`): conditions-based — exposure-band label
  (pp.304–305) + daily/weekly note + a `watch` list of regime-flip triggers
  (distance to the 67/34 cutoffs, distribution nearing topping, absent FTD, VIX
  percentile, daily↔weekly divergence, pre-market gap). Carries the literal phrase
  **"not a prediction of where price closes"** — locked.
- **Implied open = SPY/QQQ ETF pre-market print, NOT futures** (no index-futures
  feed exists). `prices.bulk_snapshot`, freshness-guarded ≤18h; `null` + "not
  wired" when unavailable. Index futures listed in `config.not_wired`.
- **Pre-open cron:** `sepa.cli market-gauge-preopen` — **Mon–Fri 8:32am ET**
  (`backend/crontab`, container TZ America/New_York) → `run_and_persist()` upserts
  Mongo `market_gauge` (`_id:"latest"`). `get_gauge()` prefers the fresh pre-open
  doc (<20h) so the **nav badge shows the morning read all day** (daily score +
  weekly chip + `pre-open HH:MM ET` stamp); `?force=true` recomputes live.
- **Code:** `sepa/market_gauge.py` (+`compute_weekly`/`_outlook`/`_premarket_gap`/
  `run_and_persist`/`load_persisted`), `sepa/cli.py`, `crontab`; FE
  `MarketGauge.tsx` (weekly section + outlook), `MarketGaugeBadge.tsx` (weekly chip
  + stamp), `useMarketGauge.ts`. `scanner.py` untouched (Rule #2).
- **Contracts:** `backend/tests/test_market_gauge.py` (weekly + outlook behavioral)
  + `test_sepa_contracts.py::test_weekly_gauge_locked` (source guard).

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
