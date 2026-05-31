# Distribution / Accumulation Methodology — Locked As Of 2026-05-31

**Why this doc exists.** Ajay trades real money off the SEPA scanner's
distribution read. The `strength` label (`strong` / `accumulating` /
`neutral` / `distributing` / `unknown`) feeds the Stage-2 → Stage-3
downgrade and the "AVOID — churning at top" flag. On 2026-05-31 we changed
how that label is decided — from a **day-count-first** rule to a
**volume-primary** rule. This doc is the source of truth for that decision so
it is not silently reverted by a future refactor that "cleans up" the logic.

The companion regression test —
`backend/tests/test_sepa_contracts.py` (the `test_distribution_*` cases) —
asserts every rule below machine-readably, and runs in `make contracts`
(the mandatory pre-commit gate). If you change a rule here, you are changing
trading logic: bump the version, update the contract test, and get explicit
sign-off.

- **Version:** 1.0 (2026-05-31)
- **Code:** `backend/sepa/volume.py` → `_strength_label()` + the threshold constants
- **Contract:** `backend/tests/test_sepa_contracts.py` → `test_distribution_*`

---

## 1. The decision in one sentence

> Per-stock distribution is decided by **volume** (up/down dollar-volume ratio
> + Chaikin Money Flow), **not** by counting distribution days. The day count
> survives only as a **gated backstop** for a slow persistent bleed, and only
> when the volume balance is also negative (`ratio < 1`).

## 2. Why — the research (Rule #1: cite, don't invent)

Minervini's books describe distribution qualitatively ("Stage 4 topping,"
"selling into strength," p.76 "down days on above-average volume") but never
give a single per-stock numeric trigger. So we looked at how the rest of the
field measures it, and the split is consistent:

| Approach | What it actually measures | Scope |
|---|---|---|
| **O'Neil / IBD "distribution days"** (4–5 down-on-volume days in ~4–5 weeks → market in trouble) | Institutional selling across the **index** | **Market timing tool**, not a per-stock label |
| **Up / Down Volume Ratio** (sum up-day vol ÷ sum down-day vol) | The **magnitude** of buying vs selling in *this* name | **Per-stock** |
| **Chaikin Money Flow** (volume weighted by where price closes in its range, −1..+1) | Buying/selling **pressure** in *this* name | **Per-stock** |
| **Accumulation/Distribution line** | Cumulative money-flow direction | **Per-stock** |

The takeaway: the famous "count to 4–5" rule is an **index** tool. Applying it
per stock over-fires on every normal pullback inside an uptrend. The per-stock
convention used by Minervini-style platforms (e.g. up/down volume ratio +
money-flow) measures the *size* of the selling, which is what actually matters
for "is this name being distributed."

So we made **volume the primary signal** and demoted the day count to a
backstop. (Decision confirmed with Ajay; he chose "Volume + count backstop"
and asked us to research it first — this is that research.)

## 3. The inputs (computed in `volume.py`)

| Symbol in spec | Field | How it's computed | Lookback |
|---|---|---|---|
| `ratio` | `up_down_vol_ratio` | Σ(volume on up-closes) ÷ Σ(volume on down-closes) | recent window |
| `cmf` | `cmf` | Σ(money-flow-volume) ÷ Σ(volume), money-flow-multiplier = `((C−L)−(H−C))/(H−L)`; range −1..+1 | 20 sessions |
| `dist_days` | `distribution_days_25` | down-close ≤ −0.2% **on above-average (50-day) volume** (book p.76) | 25 sessions |

`dist_days` symmetry note (2026-05-30 fix): both the accumulation-day and
distribution-day counters now require **above-average** (50-day) volume.
Earlier the distribution counter used "volume > yesterday," which was
asymmetric and over-counted ordinary pullbacks (the CVGI-class false-avoid).

## 4. The rule (the spec `_strength_label` MUST satisfy)

Evaluated **top to bottom**; first match wins.

```
0.  ratio is None                                            → "unknown"

1.  PRIMARY (volume outflow):
    ratio ≤ DIST_RATIO_THRESHOLD (0.70)
      OR cmf ≤ CMF_OUTFLOW_THRESHOLD (−0.10)                 → "distributing"

2.  BACKSTOP (slow bleed, volume-gated):
    dist_days ≥ DIST_DAYS_BACKSTOP (8)  AND  ratio < 1.0     → "distributing"

3.  STRONG (all three align):
    ratio ≥ ACCUM_STRONG_THRESHOLD (1.50)
      AND (cmf is None OR cmf ≥ CMF_INFLOW_THRESHOLD (0.10))
      AND dist_days ≤ 1                                       → "strong"

4.  ratio ≥ ACCUM_RATIO_THRESHOLD (1.30)                     → "accumulating"

5.  otherwise                                                → "neutral"
```

### Locked thresholds

| Constant | Value | Meaning |
|---|---|---|
| `ACCUM_RATIO_THRESHOLD` | `1.30` | up/down vol ratio for "accumulating" |
| `ACCUM_STRONG_THRESHOLD` | `1.50` | ratio for "strong" (with CMF + low dist_days) |
| `DIST_RATIO_THRESHOLD` | `0.70` | ratio at/below which volume says "distributing" |
| `CMF_INFLOW_THRESHOLD` | `+0.10` | CMF for buying pressure |
| `CMF_OUTFLOW_THRESHOLD` | `−0.10` | CMF at/below which money flow says "distributing" |
| `DIST_DAY_DOWN_PCT` | `−0.002` | a "down day" = close ≤ −0.2% |
| `DIST_DAY_LOOKBACK` | `25` | window for counting distribution days |
| `DIST_DAYS_BACKSTOP` | `8` | day count that arms the slow-bleed backstop (was a trigger-happy 4) |

## 5. The two non-negotiable invariants

These are the whole point of the change. The contract test fails if either breaks:

1. **A high day count alone never flags distribution.** If the volume balance
   is positive (`ratio ≥ 1`), no number of distribution days can make a name
   "distributing." The backstop is gated on `ratio < 1.0`.

2. **The old `dist_days >= 4` hard gate stays gone.** It must not return as
   live code (a comment documenting it is fine; the test strips comments).

## 6. Worked examples

| Case | ratio | cmf | dist_days | Result | Why |
|---|---|---|---|---|---|
| **ARM-class** (8 down days but heavy net buying) | 1.92 | +0.32 | 8 | `accumulating` | volume positive → backstop gated off; old gate wrongly said `distributing` |
| Clean leader | 1.50 | +0.20 | 2 | `accumulating` | strong needs `dist_days ≤ 1` |
| Textbook strong | 1.60 | +0.20 | 0 | `strong` | all three align |
| Heavy outflow | 0.60 | −0.20 | 5 | `distributing` | ratio ≤ 0.70 (primary) |
| CMF outflow only | 1.20 | −0.15 | 1 | `distributing` | cmf ≤ −0.10 (primary) |
| Slow bleed | 0.95 | 0.00 | 8 | `distributing` | backstop: persistent **and** ratio < 1 |
| Bleed, one day short | 0.95 | 0.00 | 7 | `neutral` | below the backstop count |
| High count, positive vol | 1.05 | 0.00 | 12 | `neutral` | invariant #1 — count alone never distributes |

## 7. Where the label is used downstream

- **Stage classifier**: a name that looks Stage-2 by moving-average geometry
  but reads `distributing` is downgraded to **Stage 3** (the "churning at the
  top" / volume-disagreement case). This is the codification of Minervini's
  qualitative Stage 3/4 descriptions (book p.71–76) — a judgment call, not a
  verbatim book formula. Documented here so that's explicit.
- **Card UI**: the `$ Distributing` flow chip + the Stage-3 volume-disagreement
  badge.

## 8. Change history

- **2026-05-31 — v1.0.** Switched `_strength_label` from count-first to
  volume-primary; demoted day count to a `ratio < 1` gated backstop; raised the
  backstop arm from `4` to `DIST_DAYS_BACKSTOP = 8`. Trigger: ARM (and similar
  leaders) were flagged `distributing` while up/down vol was 1.92 and CMF +0.32.
  Preceded by the 2026-05-30 phantom-Saturday-bar fix (which had inflated every
  name's `dist_days`) and the 2026-05-30 symmetric above-average-volume fix to
  the distribution-day counter (book p.76).
