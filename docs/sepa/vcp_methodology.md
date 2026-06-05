# VCP detector — methodology & spec

**Code:** `backend/sepa/vcp.py` (`detect(df)`)
**Contracts:** `backend/tests/test_vcp.py` (behavioral) · `tests/test_sepa_contracts.py::test_vcp_constants_locked` (source guard)
**Book:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013), Ch. 10, **pp. 197–205** (page numbers below are the book's printed pages; the repo PDF is offset +15).
**Status:** rewritten 2026-06-01 (base-window fix). Supersedes the pre-2026-06-01 whole-window logic.

---

## 1. What a VCP is (the book)

The **Volatility Contraction Pattern** is Minervini's signature footprint of a
proper base. As a stock consolidates after an advance, successive pullbacks get
**shallower from left to right** because institutions are absorbing supply
(p.205). When the contractions tighten and volume dries up, the line of least
resistance is established and the stock is ready to break out.

Key book facts the detector encodes:

| Fact | Page |
|---|---|
| A constructive base forms **after** an advance; the best correct the *least* | p.197 |
| A VCP is **2 to 6 contractions** (typically 2–4) | pp.198–199 |
| Each contraction is "**about half (± a reasonable amount)** of the previous" — e.g. 25%→15%→8% or 25%→10%→5% | pp.198–200 |
| First contraction is "say, **25 percent**"; a flat base is 10–15% | pp.198, 200 |
| Contractions get **smaller left→right as supply is absorbed** | p.205 |
| Tightness in price is accompanied by a **significant decrease in volume** | p.205 |
| A correction of **>50% is generally too much**; 25–35% is the constructive zone | p.186 |
| The buy point is the breakout **above the pivot on expanding volume** | p.203 |

---

## 2. The core idea of the rewrite

> **The base is the most recent *contracting* consolidation — not the whole
> 325-bar window.**

The pre-2026-06-01 detector measured `base_depth = (max − min) / max` across the
entire 325-bar (≈16-month) lookback. For any momentum leader — exactly the names
SEPA exists to find — that range was **60–94%**, so every one failed the
`too_deep` gate and the scanner produced **zero VCP setups**. That starved the
15-point "setup" score leg (max score capped ~79.7, so STRONG_BUY ≥85 was
unreachable) and the `is_buyable` gate (0 actionable buys).

The fix: the 325 bars are only the **horizon to search**. The actual base is the
**maximal suffix of contractions whose depths decrease left→right** (the literal
"smaller from left to right" of p.205). Depth, contraction count, tightness,
pivot quality, and volume are all measured **within that base**.

---

## 3. Algorithm

`detect(df, lookback_days=325)` →

1. **Guard:** need ≥ `lookback_days + 10` (335) bars (p.197 bases run up to ~65
   weeks; 325 bars + buffer). Else `None`.
2. **Swings:** `_find_swings(close[-325:], window=5)` → alternating highs/lows
   (a bar is a swing high/low if it's the extreme of the 5 bars on each side).
3. **Contractions:** pair each swing high with the next swing low →
   `[{top, bot, depth_pct}, …]` left→right.
4. **Isolate the recent base:** walk back from the last contraction while depths
   are (weakly) decreasing; that suffix is the base. (`while depths[m-1] >= depths[m]: m -= 1`.)
5. **Measure within the base:**
   - `base_high` = first (left) contraction's top; `base_low` = min bottom.
   - `base_depth_pct = (1 − base_low/base_high) × 100`.
   - `pivot` = last contraction's top (buy point); `stop` = last contraction's bottom.
6. **Gate** (see §4).

---

## 4. Gates — `has_base = True` requires ALL

| Gate | Rule | Book |
|---|---|---|
| `n_contractions >= 2` | it's a *contraction* pattern | pp.198–199 |
| end-to-end tightening | `final ≤ 0.6 × first` contraction depth (~half ± reasonable) | p.199 |
| `base_depth_pct >= 5` | a real pullback (below the ~5% handle = a flat line) | p.198 |
| `not too_deep` | `base_depth_pct ≤ 40%` (proper base corrects the least) | pp.186, 197 |
| `tight_right_side` | final contraction `≤ 12%` (handle ~5%, example 3%) | pp.198, 202 |
| `pivot_quality_ok` | base sits atop a ≥20% prior advance | p.197 |

Soft flags (returned, used by the scorer for a quality bonus, **not** hard gates):
`ideal_depth_range` (8–35%), `good_contraction_count` (2–6), `volume_drying`
(final/base volume < 0.8, p.205).

---

## 5. Output (return dict)

```jsonc
{
  "has_base": true,
  "base_depth_pct": 25.0,          // measured on the RECENT base
  "base_high": 100.0, "base_low": 75.0,
  "base_bars": 60,                 // bars from base start to now
  "n_contractions": 3,
  "contractions": [ {top_idx,top_price,bot_idx,bot_price,depth_pct}, … ],
  "monotonic_shrinkage": true,
  "final_vs_first_ok": true,       // end-to-end tightening
  "final_contraction_pct": 8.0,
  "tight_right_side": true,
  "volume_drying": true,
  "too_deep": false,
  "good_contraction_count": true,
  "ideal_depth_range": true,
  "pivot_buy_price": 92.0,         // -> entry_setup.pivot
  "suggested_stop": 84.6,          // -> entry_setup.stop
  "pivot_quality_ok": true,
  "pivot_prior_advance_pct": 100.0
}
```

## 6. How it feeds the scan

- `has_base == True` → `entry_setup = {type:"VCP", pivot, stop}` and the **+15**
  setup score leg (× a risk-to-stop multiplier; see the re-rank in
  `scanner._determine_setup`). A textbook VCP (`ideal_depth_range` +
  `good_contraction_count` + `volume_drying`) earns a further **+2**.
- A VCP is one of the gates of `is_buyable` (with Stage 2 + not-late + liquid +
  a volume-confirmed breakout, book p.203).
- VCP is the **most common** setup, so a healthy detector keeps STRONG_BUY and
  `is_buyable` populated. Post-fix yield on the live qualifier set: **155/514
  (~30%)**, median base depth ~17%.

## 7. Config

| Var / constant | Default | Meaning |
|---|---|---|
| `lookback_days` (arg) | 325 | search horizon (≈65 weeks) |
| `_find_swings` window | 5 | bars each side for a swing |
| too-deep / min-depth | 40% / 5% | base-depth bounds |
| tightening / tight-right | 0.6× / 12% | contraction shape |
| pivot prior advance | 20% | base-after-advance gate |

To change any threshold: edit `vcp.detect()`, update `test_vcp_constants_locked`
(source guard) and the relevant `test_vcp.py` assertion, then run
`make contracts-sepa`.

## 8. Known limits (acceptable)

- The 5-bar swing window is tight; weekly-scale "Ts" in very long bases can be
  missed. (Bias: under-detect, not over-detect — conservative.)
- First-contraction magnitude isn't a separate gate; it's captured by the
  overall `base_depth_pct` bounds.
- Off-exchange / very thin names can produce noisy swings; the liquidity gate
  upstream filters most of these before VCP runs.

## 9. Contracts

- **`backend/tests/test_vcp.py`** (8 behavioral tests on synthetic series):
  clean VCP fires; **recent-base-not-full-window regression**; deep base
  rejected; non-tightening rejected; flat line rejected; min-history `None`;
  prior-advance required; volume-drying flag.
- **`test_sepa_contracts.py::test_vcp_constants_locked`** — guards the source
  literals + the regression (`float(c.max())` must not return).
- Both run in **`make contracts-sepa`** (and the pre-commit hook).

## 10. VCP tightness score (added 2026-06-05)

A single **0-100 tightness / quality** score per VCP — "how textbook is this
base?" — surfaced as a card chip (🎯 VCP 80 · Tight), banded like the
breakoutshappen scanner: **≥70 tight (well-formed) · 40-69 developing · <40 early**.

`vcp._tightness_score(...)` aggregates the detector's already-book-grounded
pieces; the **weighting is OURS** (a presentation heuristic, NOT a Minervini
formula — each component cites the book, the blend does not):

| Component | Pts | Book |
|---|---|---|
| End-to-end tightening (final ÷ first contraction depth) | 35 | p.199 |
| Right-side handle tightness (final contraction %) | 25 | pp.198, 202 |
| Volume drying up | 20 | p.205 |
| Constructive depth (8-35%) + contraction count (2-6) | 10 | pp.198-199 |
| Proximity to the pivot | 10 | p.203 |

Returned by `detect()` as `tightness` / `tightness_band` / `tightness_drivers`.
Scored whenever ≥2 contractions exist (so developing bases band too), independent
of the strict `has_base` gate. **Display-only** — it does NOT change `has_base`,
the gates, or the composite score. Tests: `test_vcp.py::test_tightness_score_bands`
+ `::test_tightness_attached_to_detect_output`.
