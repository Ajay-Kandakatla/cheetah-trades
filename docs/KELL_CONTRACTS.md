# Oliver Kell — `/kell` Page Contracts

**Version 1.0 — 2026-05-25**
**Locked.** Do NOT modify formulas, thresholds, or output shapes below
without explicit user sign-off BEFORE any code is written. Mirrors the
governance pattern from `docs/SEPA_CONTRACTS.md` §12.

This doc captures the canonical Oliver Kell "Cycle of Price Action" (CoPA)
pattern scanners that ship in `backend/kell/`. Each scanner's input, formula,
output, and persistence shape is frozen here so future migrations can be
checked against it. The regression suite at
`backend/tests/test_kell_contracts.py` enforces these as code.

---

## §1 — What is locked

| Locked item | Lives at | Why |
|---|---|---|
| Each scanner's threshold constants | `backend/kell/<name>.py` constants block (`_*`) | If we change these the entries shift, R:R math changes, alerts fire differently |
| Each scanner's detector function name + signature | `_detect_<pattern>(symbol)` returns `dict \| None` | The API router, force-scan dispatch, and `__main__` blocks call by name |
| The 6 `kind` discriminators stored in Mongo | `wedge_drop`, `reversal_extension`, `volatility_compression`, `base_break`, `power_trend`, `climax_run` | Frontend tab routes, push notification kinds, and history queries all key on these strings |
| Setup payload shape (`store.make_setup`) | `backend/setups/store.py` | Frontend `Setup` type + setup overlay component depend on every field |
| Tier ranking (safest → most aggressive) | `frontend/src/components/KellSetupTabs.tsx` `TAB_ORDER` | UI risk gradient is left-to-right; reordering would be a behavior change |
| Climax-Run is a SELL signal, not a buy | `meta.signal_type == "SELL_OR_TAKE_PROFITS"` | Frontend rendering and any future PnL logic must NOT treat it as an entry |

## §2 — What is NOT locked (free to evolve)

- Scanner top_n values (universe slice size) — performance knob
- Push notification copy + emoji — cosmetic
- `expires_in_hours` per kind — cosmetic until it changes detection semantics
- Tier colors — UX, can be themed
- Info panel / banner copy — explanatory text, refine freely

---

## §3 — Cycle of Price Action — pattern catalogue

Kell's framework views a stock's life as a cycle that rotates through 6
recognizable shapes. We detect each one independently; a single ticker can
match multiple scanners on the same day (e.g. a Volatility Compression
candidate may also show a Base & Break breakout on the day it triggers).

```
        ┌─ Wedge Drop (pullback shakeout)
        │
        ↓
   Reversal Extension (post-low turn)
        │
        ↓
   Volatility Compression (tight contraction)
        │
        ↓
   Base & Break (textbook breakout)
        │
        ↓
   Power Trend (stair-step continuation)
        │
        ↓
   Climax Run (blow-off — defensive SELL signal)
        │
        ↓
        └─→ cycle repeats from Wedge Drop
```

---

## §4 — Scanner contracts

### 4.1 `wedge_drop` — SAFE-MOD

**File:** `backend/kell/wedge_drop.py`
**Tier:** SAFE-MOD (🟢)
**Signal:** BUY (entry setup)
**Universe:** top 200 SEPA candidates

| Constant | Value | Purpose |
|---|---|---|
| `_WEDGE_MIN_LEN` | 3 | Min wedge length in sessions |
| `_WEDGE_MAX_LEN` | 7 | Max wedge length in sessions |
| `_MA_TOUCH_TOLERANCE_PCT` | 2.0 | df[-1].low within X% of MA21/MA50 |
| `_MIN_VOL_RATIO` | 0.7 | df[-1].volume ≥ 0.7 × avg_volume_50 |
| `_AVG_VOL_WINDOW` | 50 | Average-volume baseline |
| `expires_in_hours` | 72 | Validity window |

**Detection (all conditions must be true):**

1. Recent 3-7 day descending wedge: `highs[-N:-1]` strictly descending AND `lows[-N:-1]` strictly descending
2. df[-1].low within 2% of MA21 OR MA50 (key support test)
3. df[-1] is a bullish reversal candle: `close > open AND close > df[-2].close`
4. df[-1].volume ≥ 0.7 × 50d average (volume confirms reversal)

**Trigger:** `df[-1].high + 0.01`
**Stop:** `df[-1].low - 0.01`
**Target:** `trigger × 1.08`

---

### 4.2 `reversal_extension` — AGGRESSIVE

**File:** `backend/kell/reversal_extension.py`
**Tier:** AGGRESSIVE (🟠)
**Signal:** BUY
**Universe:** top 200 SEPA candidates

| Constant | Value | Purpose |
|---|---|---|
| `_LOW_LOOKBACK` | 20 | idx_low lies within last 20 sessions |
| `_LOW_MIN_AGE` | 3 | Low must be ≥ 3 sessions ago (not today) |
| `_PRIOR_HIGH_WIN` | 5 | 5-day prior high must be cleared |
| `_MIN_VOL_MULT` | 1.5 | df[-1].volume vs 50d avg |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `expires_in_hours` | 96 | Validity window |

**Detection:**

1. Find `idx_low` = index of lowest low in last 20 sessions
2. `idx_low` is at least 3 sessions ago (not today's bar)
3. `df[-1].close > max(highs[-6:-1])` (extension above 5-day prior high)
4. `df[-1].close > df[-1].open` (bullish close)
5. `df[-1].volume > 1.5 × 50d_avg_volume`

**Trigger:** `df[-1].close × 1.005`
**Stop:** `df[idx_low].low - 0.01`
**Target:** `trigger × 1.15`

---

### 4.3 `volatility_compression` — SAFE

**File:** `backend/kell/volatility_compression.py`
**Tier:** SAFE (🟢)
**Signal:** BUY (breakout-ready setup)
**Universe:** top 150 SEPA candidates

| Constant | Value | Purpose |
|---|---|---|
| `_ATR_SHORT_WIN` | 10 | Short ATR window |
| `_ATR_LONG_WIN` | 50 | Long ATR window |
| `_ATR_RATIO_MAX` | 0.7 | ATR_10 ≤ 0.7 × ATR_50 (compression) |
| `_RANGE_WIN` | 5 | Last-N-day range window |
| `_RANGE_MAX_PCT` | 0.04 | 5-day range ≤ 4% of close |
| `_MA_PROX_PCT` | 0.05 | Within 5% of MA20 OR MA50 |
| `_VOL_DRY_RATIO` | 0.85 | 10d avg vol < 0.85 × 50d avg vol |
| `expires_in_hours` | 120 | Validity window |

**Detection (all must be true):**

1. `ATR_10 / ATR_50 ≤ 0.7` (volatility contracting)
2. `(highs[-5:].max() - lows[-5:].min()) ≤ 0.04 × close` (tight 5-day range)
3. `|close - MA20| / MA20 ≤ 0.05` OR `|close - MA50| / MA50 ≤ 0.05` (sitting on key MA)
4. `mean(volume[-10:]) / mean(volume[-50:]) ≤ 0.85` (volume drying)

**Trigger:** `highs[-5:].max() × 1.005`
**Stop:** `lows[-5:].min() - 0.01`
**Target:** `trigger × 1.10`

---

### 4.4 `base_break` — MODERATE

**File:** `backend/kell/base_break.py`
**Tier:** MODERATE (🟡)
**Signal:** BUY
**Universe:** top 200 SEPA candidates

| Constant | Value | Purpose |
|---|---|---|
| `_PIVOT_LOOKBACK` | 30 | Sessions used for pivot resistance (excluding today) |
| `_STOP_LOOKBACK` | 15 | Sessions used for stop floor |
| `_MIN_VOL_MULT` | 1.5 | Breakout volume threshold |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `expires_in_hours` | 48 | Short window — already broken out |

**Detection:**

1. `pivot = max(highs[-31:-1])` (30-day high, excluding today)
2. `df[-1].close > pivot` (breakout TODAY)
3. `df[-1].volume > 1.5 × 50d_avg_volume`
4. Stage 2 (already filtered via SEPA universe upstream)

**Trigger:** `pivot + 0.01`
**Stop:** `min(lows[-15:])`
**Target:** `trigger × 1.10`

---

### 4.5 `power_trend` — AGGRESSIVE

**File:** `backend/kell/power_trend.py`
**Tier:** AGGRESSIVE (🟠)
**Signal:** BUY (continuation)
**Universe:** top 200 SEPA candidates

| Constant | Value | Purpose |
|---|---|---|
| `_TREND_WIN` | 50 | Closes above MA50 required for N bars |
| `_HH_LOOKBACK` | 30 | Higher-high search window |
| `_HH_MIN_COUNT` | 2 | Minimum distinct higher highs |
| `_PULLBACK_MAX_PCT` | 10.0 | Pullbacks between HH must be < 10% |
| `_MA21_TOUCH_LOOKBK` | 5 | Last pullback bottomed at MA21 within N sessions |
| `_MA21_TOUCH_PCT` | 2.5 | "Touched" tolerance (low within X% of MA21) |
| `expires_in_hours` | 96 | Validity window |

**Detection:**

1. `closes[-50:].min() > MA50_at_each_day` (strict trend — all 50 bars above MA50)
2. `df[-1].close > MA21`
3. ≥ 2 distinct higher-highs in last 30 sessions, each separated by a pullback of < 10%
4. Latest pullback bottomed at MA21 (low within 2.5% of MA21) within last 5 sessions

**Trigger:** `df[-1].close × 1.005`
**Stop:** `MA21 × 0.98`
**Target:** `trigger × 1.12`

---

### 4.6 `climax_run` — DEFENSIVE (warning)

**File:** `backend/kell/climax_run.py`
**Tier:** MOST AGGRESSIVE / WARN (🔴)
**Signal:** ⚠ SELL_OR_TAKE_PROFITS — **NOT a buy setup**
**Universe:** top 200 SEPA candidates
**Bear-regime gate:** intentionally NOT applied — blow-off warnings are
arguably MORE valuable in a bear regime.

| Constant | Value | Purpose |
|---|---|---|
| `_RUN_WIN` | 30 | Run window for 30-session return |
| `_MIN_RUN_PCT` | 50.0 | Minimum 30-session run % |
| `_MIN_RANGE_RATIO` | 0.05 | Bar range / close > 5% (wide-range bar) |
| `_MIN_VOL_MULT` | 2.5 | Volume vs 50d avg |
| `_MIN_MA50_STRETCH` | 0.30 | Close 30%+ above MA50 (stretched) |
| `_LOWER_THIRD_RATIO` | 0.333 | Close in lower 1/3 of bar range |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `expires_in_hours` | 48 | Validity window |

**Detection:**

1. 30-session return > 50%
2. df[-1] is wide-range: `(high - low) / close > 0.05`
3. df[-1].volume > 2.5 × 50d_avg_volume
4. Either: `df[-1].close < df[-1].open` (red candle / distribution day)
   OR `df[-1].close` in lower 1/3 of `(low, high)` range
5. `(close - MA50) / MA50 > 0.30` (price 30%+ above MA50, stretched)

**Output (no trigger/target — it's a sell signal):**
```python
{
    "trigger":  df[-1].low,     # alert level
    "stop":     0,
    "target":   0,
    "meta": {
        "signal_type":   "SELL_OR_TAKE_PROFITS",
        "run_30d_pct":   ...,
        "vol_mult":      ...,
        "ma50_stretch":  ...,
    },
}
```

---

## §5 — Output payload shape (frozen)

Every scanner emits via `setups.store.make_setup(kind=..., ...)`. The
resulting Mongo document — and the JSON the frontend consumes via
`GET /setups/{kind}` — has this exact shape:

```typescript
{
  _id:           string,          // Mongo ObjectId
  kind:          string,          // one of the 6 Kell kinds (or any setups/* kind)
  symbol:        string,          // uppercase ticker
  generated_at:  number,          // epoch seconds when the setup was emitted
  date_et:       string,          // "YYYY-MM-DD" in US Eastern
  trigger:       number,          // entry price (rounded to 4 decimals)
  stop:          number,          // stop-loss price (0 for climax_run)
  target:        number,          // first take-profit (0 for climax_run)
  risk_pct:      number,          // (trigger-stop)/trigger × 100
  reward_pct:    number,          // (target-trigger)/trigger × 100
  rr:            number,          // reward_pct / risk_pct
  meta:          object,          // scanner-specific fields — see §6
  status:        "pending" | "triggered" | "expired" | "stopped",
  triggered_at:  number | null,
  expires_at:    number,          // epoch seconds when sweeper flips to expired
}
```

These keys MUST stay stable — the frontend `Setup` type at
`frontend/src/hooks/useSetupsByKind.ts` and `SetupOverlayStrip.tsx`
references them directly.

---

## §6 — Per-scanner `meta` field contract

Each scanner attaches a fixed set of meta fields. Adding new meta fields is
allowed and additive; **removing or renaming existing fields is a breaking
change** to the chat-context payload and the future Kell drill-in modal.

### 6.1 `wedge_drop.meta`
```
{
  wedge_len:           int,         # number of sessions in the wedge
  ma_touch:            "ma21" | "ma50",
  ma_touch_pct:        float,       # how close to the MA the low got
  reversal_strength:   float,       # df[-1].close - df[-1].open (absolute $)
  vol_ratio:           float,       # df[-1].volume / 50d_avg
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

### 6.2 `reversal_extension.meta`
```
{
  idx_low_days_ago:    int,
  prior_5d_high:       float,
  extension_pct:       float,       # df[-1].close vs prior 5d high
  vol_mult:            float,
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

### 6.3 `volatility_compression.meta`
```
{
  atr_ratio:           float,       # ATR_10 / ATR_50
  range_pct:           float,       # 5-day range / close
  ma_anchor:           "ma20" | "ma50",
  ma_distance_pct:     float,       # |close - MA| / MA
  vol_dry_ratio:       float,       # 10d_avg_vol / 50d_avg_vol
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

### 6.4 `base_break.meta`
```
{
  pivot:               float,
  breakout_pct:        float,       # (close - pivot) / pivot × 100
  vol_mult:            float,
  base_low:            float,       # min(lows[-15:])
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

### 6.5 `power_trend.meta`
```
{
  higher_high_count:   int,
  last_pullback_pct:   float,
  ma21_touch_days_ago: int,
  trend_age_days:      int,         # consecutive days closes > MA50
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

### 6.6 `climax_run.meta`
```
{
  signal_type:         "SELL_OR_TAKE_PROFITS",   # FIXED literal
  run_30d_pct:         float,
  range_ratio:         float,
  vol_mult:            float,
  ma50_stretch:        float,
  close_pos_in_range:  float,        # (close - low) / (high - low), 0=low 1=high
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

---

## §7 — Frontend tier ordering (locked)

`frontend/src/components/KellSetupTabs.tsx` `TAB_ORDER` must remain:

```typescript
const TAB_ORDER: KellTab[] = [
  'all',                       // neutral
  'volatility_compression',    // SAFE       (🟢)
  'wedge_drop',                // SAFE-MOD   (🟢)
  'base_break',                // MODERATE   (🟡)
  'reversal_extension',        // AGGRESSIVE (🟠)
  'power_trend',               // AGGRESSIVE (🟠)
  'climax_run',                // WARN       (🔴)
];
```

The tier color gradient (green → red) communicates risk left-to-right.
Reordering would be a UX behavior change.

---

## §8 — API surface (locked)

The following endpoints serve Kell data. None are Kell-specific — they
share `backend/setups/api.py` with the existing PEG/Bull-Flag/etc routes:

```
GET  /setups/{kind}?only_pending=true&limit=100
       → { kind, count, setups: [...] }
       kind ∈ §1 locked discriminators

POST /setups/{kind}/scan
       admin only — force re-run a scanner

POST /setups/expire-stale
       admin only — sweep past-expires_at rows to "expired"
```

Adding fields to the response is fine. Removing the `kind`, `count`, or
`setups` top-level keys is a breaking change.

---

## §9 — Universe (locked behavior)

Kell scanners pull from `setups.universe.get_sepa_candidates(top_n=N)`
which:

1. Loads the most recent SEPA history scan
2. Filters to ratings ∈ `{STRONG_BUY, BUY, WATCH}`
3. Falls back to `all_results` (broader pool) when `candidates` is empty
4. Returns up to `top_n` rows sorted by score descending

**This is shared with the SEPA setup tabs and PEG/Bull-Flag scanners.**
A change here cascades to every scanner. Modify only with explicit
sign-off in BOTH this doc and `docs/SEPA_CONTRACTS.md`.

---

## §10 — Cron schedule (locked behavior; times can move)

Six cron entries in `backend/crontab` run Mon-Fri evenings ET, sequentially
after the 16:30 SEPA fast-scan completes:

```
5      19    *    *    1-5  /usr/local/bin/python -m kell.wedge_drop
10     19    *    *    1-5  /usr/local/bin/python -m kell.reversal_extension
15     19    *    *    1-5  /usr/local/bin/python -m kell.volatility_compression
20     19    *    *    1-5  /usr/local/bin/python -m kell.base_break
25     19    *    *    1-5  /usr/local/bin/python -m kell.power_trend
30     19    *    *    1-5  /usr/local/bin/python -m kell.climax_run
```

The 5-minute spacing avoids piling all six scanners on Massive in the same
second. Acceptable to shift these times — but they must run AFTER the
17:30 SEPA fast-scan completes, otherwise they read yesterday's SEPA list.

---

## §11 — Governance

| Rule | Owner |
|---|---|
| The 6 kind discriminators are PERMANENT identifiers. Renaming requires a Mongo migration script + frontend route rewrite. | Repository owner |
| Adding new Kell scanners is allowed. Update §3 + §4 + §6 here, add the file, add cron, add tab. | Code review |
| Changing scanner thresholds (constants in §4) requires an entry in `docs/changelogs/` documenting the before/after AND a backtest showing the change improves outcomes. | Repository owner |
| Removing a scanner is a major version bump. Mark deprecated in this doc for ≥30 days first. | Repository owner |
| The `climax_run` signal type literal `"SELL_OR_TAKE_PROFITS"` is referenced by frontend rendering — never change without coordinated frontend update. | Repository owner |

---

## §12 — How to verify

Run the regression suite:

```sh
docker compose exec api python -m pytest /app/tests/test_kell_contracts.py -v
```

All tests in `backend/tests/test_kell_contracts.py` must pass before AND
after any Kell-adjacent migration. The tests assert:

- Constants in §4 are unchanged
- Each detector function is importable + callable on a fake DataFrame
- Output payload from `store.make_setup` has the §5 keys
- The 6 kind discriminators are accepted by `setups.api`
- `climax_run` always emits `meta.signal_type == "SELL_OR_TAKE_PROFITS"`
- Tier ordering in `KellSetupTabs.tsx` matches §7
