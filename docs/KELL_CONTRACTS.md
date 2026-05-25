# Oliver Kell — `/kell` Page Contracts

**Version 2.0 — 2026-05-25**
**Locked.** Do NOT modify formulas, thresholds, or output shapes below
without explicit user sign-off BEFORE any code is written. Mirrors the
governance pattern from `docs/SEPA_CONTRACTS.md` §12.

This doc captures the canonical Oliver Kell "Cycle of Price Action" (CoPA)
pattern scanners that ship in `backend/kell/`. Each scanner's input, formula,
output, and persistence shape is frozen here so future migrations can be
checked against it. The regression suite at
`backend/tests/test_kell_contracts.py` enforces these as code.

**Source of truth:** Oliver Kell, *Victory in Stock Trading* (2021),
chapters 3–4 (pp. 14–27). Page references in each scanner section.

**Version 2.0 — what changed from v1.0:**
v1.0 shipped six scanners (`wedge_drop`, `reversal_extension`,
`volatility_compression`, `base_break`, `power_trend`, `climax_run`)
whose formulas were inferred rather than derived from the book. v2.0
replaces them with the six canonical CoPA phases in the order Kell
teaches them (book p. 19, "Phase 3" overview chart):

| v1.0 (deprecated) | v2.0 (canonical) | Source pages |
|---|---|---|
| `reversal_extension` (kept) | `reversal_extension` (rewritten) | pp. 16, 22-23 |
| `wedge_drop` (kept; rewritten — now BEARISH) | `wedge_pop` (new) | pp. 17, 23-24 |
| (none) | `ema_crossback` (new) | pp. 18, 23, 27 |
| `base_break` | `base_n_break` | pp. 18-19, 24, 39 |
| `climax_run` | `exhaustion_extension` | pp. 19, 25, 40 |
| `volatility_compression`, `power_trend` (deleted) | `wedge_drop` (rewritten) | pp. 18, 20, 24, 41 |

The set of `kind` discriminators has changed; this is a breaking change
for any Mongo rows persisted under v1.0 names. The Mongo `setups`
collection has a TTL via `expires_at`, so v1.0 rows roll off naturally
without a migration.

---

## §1 — What is locked

| Locked item | Lives at | Why |
|---|---|---|
| Each scanner's threshold constants | `backend/kell/<name>.py` constants block (`_*`) | If we change these the entries shift, R:R math changes, alerts fire differently |
| Each scanner's detector function name + signature | `_detect(symbol)` returns `dict \| None` | The API router, force-scan dispatch, and `__main__` blocks call by name |
| The 6 `kind` discriminators stored in Mongo | `reversal_extension`, `wedge_pop`, `ema_crossback`, `base_n_break`, `exhaustion_extension`, `wedge_drop` | Frontend tab routes, push notification kinds, and history queries all key on these strings |
| Setup payload shape (`store.make_setup`) | `backend/setups/store.py` | Frontend `Setup` type + setup overlay component depend on every field |
| Tier ranking (safest → most aggressive) | `frontend/src/components/KellSetupTabs.tsx` `TAB_ORDER` | UI risk gradient is left-to-right; reordering would be a behavior change |
| `exhaustion_extension` AND `wedge_drop` are SELL signals, not buys | `meta.signal_type == "SELL_OR_TAKE_PROFITS"` | Frontend rendering and any future PnL logic must NOT treat them as entries |
| Canonical moving averages | 10 EMA, 20 EMA, 50 SMA, 200 SMA (book p. 12) | Re-derived per scanner. Do not substitute 21 EMA, MA50/MA200, etc. |

## §2 — What is NOT locked (free to evolve)

- Scanner top_n values (universe slice size) — performance knob
- Push notification copy + emoji — cosmetic
- `expires_in_hours` per kind — cosmetic until it changes detection semantics
- Tier colors — UX, can be themed
- Info panel / banner copy — explanatory text, refine freely

---

## §3 — Cycle of Price Action — pattern catalogue

Kell's framework (book pp. 14-27) views a stock's life as a six-phase
cycle that repeats. A single ticker can match multiple scanners on the
same day (e.g. an EMA Crossback candidate may also become a Base n' Break
once the consolidation completes).

```
        ┌─ Reversal Extension (Phase 1: capitulation bottom)
        │
        ↓
   Wedge Pop (Phase 2: first reclaim of 10/20 EMA)
        │
        ↓
   EMA Crossback (Phase 3: first pullback in new uptrend)
        │
        ↓
   Base n' Break (Phase 4: longer consolidation breakout)
        │
        ↓
   Exhaustion Extension (Phase 5: 2nd-3rd extension — SELL signal)
        │
        ↓
   Wedge Drop (Phase 6: cycle end — SELL signal)
        │
        ↓
        └─→ cycle repeats from Reversal Extension
```

---

## §4 — Scanner contracts

### 4.1 `reversal_extension` — AGGRESSIVE  (per pp. 16, 22-23)

**File:** `backend/kell/reversal_extension.py`
**Signal:** BUY (entry setup) | **Tier:** AGGRESSIVE 🟠
**Universe:** top 200 SEPA candidates
**Bear-regime gated:** yes

| Constant | Value | Purpose |
|---|---|---|
| `_DOWNTREND_MIN_DAYS` | 5 | Closes below 10 EMA for at least last N sessions |
| `_EXTENSION_MIN_PCT` | 0.05 | Today's low ≥5% below 10 EMA |
| `_MIN_VOL_MULT` | 1.5 | df[-1].volume vs 50d avg |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `_HTF_SUPPORT_PCT` | 0.03 | Within 3% of 50 SMA or 200 SMA (informational) |
| `expires_in_hours` | 96 | Validity window |

**Detection (all conditions must be true):**

1. Closes below the 10 EMA for at least 5 of the most recent prior sessions.
2. `(ema10 − df[-1].low) / ema10 ≥ 0.05`  (extended below 10 EMA).
3. Bullish reversal bar: `close > open` AND (`close > df[-2].high` OR `close > (high + low) / 2`).
4. `df[-1].volume > 1.5 × avg_volume_50`.

**Trigger / Stop / Target (per pp. 47-51):**
- trigger = `df[-1].high + 0.01`
- stop = `df[-1].low − 0.01`
- target = `20 EMA` ("20 EMA on trading timeframe" — pp. 26-27)

---

### 4.2 `wedge_pop` — MODERATE  (per pp. 17, 23-24)

**File:** `backend/kell/wedge_pop.py`
**Signal:** BUY (entry setup) | **Tier:** MODERATE 🟡
**Universe:** top 200 SEPA candidates
**Bear-regime gated:** yes

| Constant | Value | Purpose |
|---|---|---|
| `_DOWNTREND_WIN` | 14 | "Recent downtrend" window |
| `_EMA_CLUSTER_MAX_PCT` | 0.02 | `|ema10 - ema20| / ema20 < 2%` |
| `_WEDGE_MIN_LEN` | 5 | Min wedge length |
| `_WEDGE_MAX_LEN` | 10 | Max wedge length |
| `_FIRST_CLOSE_LOOKBACK` | 10 | First close above BOTH EMAs in N sessions |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `_STOP_LOOKBACK` | 7 | Stop = `min(lows[-7:])` |
| `expires_in_hours` | 72 | Validity window |

**Detection:**

1. Recent downtrend: `mean(close[-15:-1]) < mean(ema20[-15:-1])`.
2. EMA cluster: `|ema10 - ema20| / ema20 < 0.02`.
3. Tight 5-10 day wedge: progressively higher lows AND ranges contracting.
4. Today: `close > ema10 AND close > ema20` — first such close in last 10 sessions.
5. Bullish: `close > open`.
6. Volume: `df[-1].volume ≥ avg_volume_50` (at or above average).

**Trigger / Stop / Target:**
- trigger = `df[-1].high + 0.01`
- stop = `min(lows[-7:])`
- target = `df[-1].close × 1.10`

---

### 4.3 `ema_crossback` — SAFE-MOD  (per pp. 18, 23, 27)

**File:** `backend/kell/ema_crossback.py`
**Signal:** BUY (entry setup) | **Tier:** SAFE-MOD 🟢
**Universe:** top 200 SEPA candidates
**Bear-regime gated:** yes

| Constant | Value | Purpose |
|---|---|---|
| `_TREND_WIN` | 15 | "Established uptrend" window |
| `_TREND_MIN_CLOSES` | 10 | ≥10 of last 15 closes above 10 EMA |
| `_EMA10_RISING_DAYS` | 10 | 10 EMA has been rising for N sessions |
| `_PULLBACK_LOOKBACK` | 3 | EMA touch within last N sessions |
| `_EMA_TOUCH_PCT` | 0.01 | Low within 1% of ema10 or ema20 |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `_LIGHT_VOL_WINDOW` | 3 | `mean(volume[-3:]) < avg_volume_50` |
| `expires_in_hours` | 72 | Validity window |

**Detection:**

1. Uptrend stack: `ema10 > ema20 > sma50` AND ≥10 of last 15 closes above 10 EMA.
2. 10 EMA has been rising for at least 10 sessions.
3. At least one of the last 3 sessions had `low ≤ ema10×1.01` OR `low ≤ ema20×1.01`.
4. Today: `close > open` AND `close > ema10`.
5. Light volume: `mean(volume[-3:]) < avg_volume_50`.

**Trigger / Stop / Target (per pp. 49 "10/20 EMA Trailing Stop"):**
- trigger = `df[-1].high + 0.01`
- stop = `min(ema20, df[-3:].low.min()) − 0.01`
- target = `df[-1].close × 1.08`

---

### 4.4 `base_n_break` — SAFE  (per pp. 18-19, 24, 39)

**File:** `backend/kell/base_n_break.py`
**Signal:** BUY (entry setup) | **Tier:** SAFE 🟢
**Universe:** top 200 SEPA candidates
**Bear-regime gated:** yes

| Constant | Value | Purpose |
|---|---|---|
| `_BASE_MIN_LEN` | 5 | Min base length |
| `_BASE_MAX_LEN` | 15 | Max base length |
| `_BASE_MAX_RANGE_PCT` | 0.10 | Base range ≤ 10% of price |
| `_BASE_NEAR_EMA_PCT` | 0.03 | Closes within 3% of ema10 or ema20 |
| `_BASE_VOL_DRY_RATIO` | 0.85 | `mean(vol_in_base) < 0.85 × avg_vol_50` |
| `_BREAKOUT_VOL_MULT` | 1.3 | `df[-1].volume > 1.3 × avg_vol_50` |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `_TREND_STACK_DAYS` | 5 | EMA stack required for N days |
| `expires_in_hours` | 48 | Short window — already broken out |

**Detection:**

1. Uptrend stack `ema10 > ema20 > sma50` for last 5 sessions.
2. Find longest valid base N∈[5,15] where: range ≤ 10% AND every close within 3% of ema10/ema20 AND volume drying.
3. Today: `df[-1].close > max(base_highs)`.
4. `df[-1].volume > 1.3 × avg_vol_50`.

**Trigger / Stop / Target (per pp. 48-49):**
- trigger = `max(base_highs) + 0.01`
- stop = `min(ema20, min(base_lows)) − 0.01`
- target = `trigger × 1.10`

---

### 4.5 `exhaustion_extension` — DEFENSIVE / WARN  (per pp. 19, 25, 40)

**File:** `backend/kell/exhaustion_extension.py`
**Signal:** ⚠ **SELL_OR_TAKE_PROFITS — NOT a buy setup** | **Tier:** DEFENSIVE 🔴
**Universe:** top 200 SEPA candidates
**Bear-regime gated:** **intentionally NOT applied** — warnings matter
in any regime.

| Constant | Value | Purpose |
|---|---|---|
| `_TREND_AGE_WIN` | 30 | Uptrend search window |
| `_TREND_AGE_MIN` | 20 | Closes above 10 EMA for ≥20 of last 30 |
| `_EXT_MIN_PCT` | 0.08 | Close ≥8% above 10 EMA |
| `_WIDE_RANGE_MIN` | 0.05 | `(high - low) / close > 5%` |
| `_MIN_VOL_MULT` | 2.0 | `df[-1].volume > 2.0 × avg_vol_50` |
| `_EXT_COUNT_WIN` | 60 | Count prior extensions in last N sessions |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `expires_in_hours` | 48 | Validity window |

**Detection:**

1. Closes above 10 EMA for ≥20 of last 30 sessions (uptrend established).
2. Today: `(close - ema10) / ema10 ≥ 0.08`.
3. Wide range: `(high - low) / close > 0.05`.
4. Volume: `df[-1].volume > 2.0 × avg_volume_50`.
5. Either close in upper half of range OR `close < open` (bearish reversal).
6. Count of distinct extension events in last 60 sessions (including today). The Nth extension is increasingly actionable per Kell — 1st can be held through, 2nd is "start scaling out," 3rd is "lock in gains."

**Output (no entry — SELL signal):**
```python
{
    "trigger": df[-1].low,      # alert level
    "stop":    0,
    "target":  0,
    "meta": {
        "signal_type":     "SELL_OR_TAKE_PROFITS",
        "extension_pct":   ...,
        "extension_count": ...,  # 1st/2nd/3rd extension
        "vol_mult":        ...,
        "range_ratio":     ...,
        "trend_age_days":  ...,
    }
}
```

---

### 4.6 `wedge_drop` — DEFENSIVE / WARN  (per pp. 18, 20, 24, 41)

**File:** `backend/kell/wedge_drop.py`
**Signal:** ⚠ **SELL_OR_TAKE_PROFITS — NOT a buy setup** | **Tier:** DEFENSIVE 🔴
**Universe:** top 200 SEPA candidates
**Bear-regime gated:** **intentionally NOT applied** — warnings matter
in any regime.

| Constant | Value | Purpose |
|---|---|---|
| `_EXHAUSTION_LOOKBACK_MIN` | 5 | Extension at least N sessions ago |
| `_EXHAUSTION_LOOKBACK_MAX` | 15 | ... and at most N sessions ago |
| `_EXT_MIN_PCT` | 0.08 | Historical extension threshold |
| `_EXT_MIN_VOL_MULT` | 2.0 | Historical extension volume threshold |
| `_FIRST_CLOSE_LOOKBACK` | 10 | First close BELOW both EMAs in N sessions |
| `_MIN_VOL_MULT` | 1.3 | Today's vol > 1.3 × avg_vol_50 |
| `_AVG_VOL_WINDOW` | 50 | Volume baseline |
| `expires_in_hours` | 72 | Validity window |

**Detection:**

1. An Exhaustion Extension exists in last 5–15 sessions (proxy: wide-range bar with vol > 2.0× avg and close >8% above 10 EMA at that bar).
2. Today: `close < ema10 AND close < ema20` — first such close in last 10 sessions.
3. Bearish: `close < open` AND `close < df[-2].close`.
4. `df[-1].volume > 1.3 × avg_volume_50`.

**Output (no entry — SELL signal):**
```python
{
    "trigger": df[-1].low,
    "stop":    0,
    "target":  0,
    "meta": {
        "signal_type":         "SELL_OR_TAKE_PROFITS",
        "exhaustion_days_ago": ...,
        "drop_pct":            ...,
        "vol_mult":            ...,
    }
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
  stop:          number,          // stop-loss price (0 for SELL signals)
  target:        number,          // first take-profit (0 for SELL signals)
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

### 6.1 `reversal_extension.meta`
```
{
  ema10:              float,
  ema20:              float,         # the target price
  sma50:              float,
  sma200:             float,
  extension_pct:      float,         # how far below 10 EMA the low was, %
  vol_mult:           float,
  engulfs_prior:      bool,
  closes_upper_half:  bool,
  near_50_sma:        bool,
  near_200_sma:       bool,
  sepa_score:         float,
  sepa_rating:        string,
  rs_rank:            int,
}
```

### 6.2 `wedge_pop.meta`
```
{
  ema10:               float,
  ema20:               float,
  ema_gap_pct:         float,        # |ema10-ema20| / ema20, %
  wedge_len:           int,
  vol_mult:            float,
  close_above_ema10:   float,        # %
  close_above_ema20:   float,        # %
  wedge_floor:         float,        # the stop
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

### 6.3 `ema_crossback.meta`
```
{
  ema10:                    float,
  ema20:                    float,
  sma50:                    float,
  touch_ma:                 "ema10" | "ema20",
  closes_above_10ema_15d:   int,
  pullback_vol_ratio:       float,   # mean(vol[-3:]) / avg_vol_50
  close:                    float,
  pullback_low:             float,
  sepa_score:               float,
  sepa_rating:              string,
  rs_rank:                  int,
}
```

### 6.4 `base_n_break.meta`
```
{
  base_len:            int,
  pivot:               float,
  base_low:            float,
  range_pct:           float,        # base range / price, %
  ema_anchor_pct:      float,        # max |close-EMA|/EMA in base, %
  vol_dry_ratio:       float,        # mean(vol_in_base) / avg_vol_50
  breakout_vol_mult:   float,
  ema20:               float,
  close:               float,
  sepa_score:          float,
  sepa_rating:         string,
  rs_rank:             int,
}
```

### 6.5 `exhaustion_extension.meta`
```
{
  signal_type:        "SELL_OR_TAKE_PROFITS",  # FIXED literal
  extension_pct:      float,
  extension_count:    int,           # 1st/2nd/3rd extension since trend start
  vol_mult:           float,
  range_ratio:        float,
  trend_age_days:     int,
  upper_half_close:   bool,
  bearish_close:      bool,
  ema10:              float,
  close, high, low, open: float,
  sepa_score:         float,
  sepa_rating:        string,
  rs_rank:            int,
}
```

### 6.6 `wedge_drop.meta`
```
{
  signal_type:         "SELL_OR_TAKE_PROFITS",  # FIXED literal
  exhaustion_days_ago: int,
  exhaustion_ext_pct:  float,
  drop_pct:            float,        # how far below the mean-EMA we closed, %
  vol_mult:            float,
  ema10:               float,
  ema20:               float,
  close:               float,
  open:                float,
  prev_close:          float,
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
  'all',                      // neutral
  'base_n_break',             // SAFE       (🟢)
  'ema_crossback',            // SAFE-MOD   (🟢)
  'wedge_pop',                // MODERATE   (🟡)
  'reversal_extension',       // AGGRESSIVE (🟠)
  'exhaustion_extension',     // WARN       (🔴) — SELL signal
  'wedge_drop',               // WARN       (🔴) — SELL signal
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
5      19    *    *    1-5  /usr/local/bin/python -m kell.reversal_extension
10     19    *    *    1-5  /usr/local/bin/python -m kell.wedge_pop
15     19    *    *    1-5  /usr/local/bin/python -m kell.ema_crossback
20     19    *    *    1-5  /usr/local/bin/python -m kell.base_n_break
25     19    *    *    1-5  /usr/local/bin/python -m kell.exhaustion_extension
30     19    *    *    1-5  /usr/local/bin/python -m kell.wedge_drop
```

The 5-minute spacing avoids piling all six scanners on Massive in the
same second. Acceptable to shift these times — but they must run AFTER
the 16:30 SEPA fast-scan completes, otherwise they read yesterday's
SEPA list.

---

## §11 — Governance

| Rule | Owner |
|---|---|
| The 6 kind discriminators are PERMANENT identifiers. Renaming requires a Mongo migration script + frontend route rewrite. | Repository owner |
| Adding new Kell scanners is allowed. Update §3 + §4 + §6 here, add the file, add cron, add tab. | Code review |
| Changing scanner thresholds (constants in §4) requires an entry in `docs/changelogs/` documenting the before/after AND a backtest showing the change improves outcomes. | Repository owner |
| Removing a scanner is a major version bump. Mark deprecated in this doc for ≥30 days first. | Repository owner |
| The SELL signal literal `"SELL_OR_TAKE_PROFITS"` in `exhaustion_extension` and `wedge_drop` is referenced by frontend rendering — never change without coordinated frontend update. | Repository owner |
| Bullish scanners (Reversal Extension, Wedge Pop, EMA Crossback, Base n' Break) are bull-regime gated. Bearish scanners (Exhaustion Extension, Wedge Drop) are NOT — warnings matter in any regime. | Repository owner |

---

## §12 — How to verify

Run the regression suite:

```sh
docker compose exec api python -m pytest /app/tests/test_kell_contracts.py -v
```

All tests in `backend/tests/test_kell_contracts.py` must pass before AND
after any Kell-adjacent migration. The tests assert:

- Constants in §4 are unchanged
- Each detector function is importable + callable
- Output payload from `store.make_setup` has the §5 keys
- The 6 kind discriminators are accepted by `setups.api`
- `exhaustion_extension` AND `wedge_drop` always emit `meta.signal_type == "SELL_OR_TAKE_PROFITS"`
- `kell.__all__` exports the 6 canonical scanners
- `backend/crontab` has a cron entry for each
