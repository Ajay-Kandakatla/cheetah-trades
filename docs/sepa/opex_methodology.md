# OpEx panel — expiration mechanics for one ticker

**What it shows** (options-flow tab, per ticker): the **nearest expiration** + its
type (weekly / monthly 3rd-Friday / quad-witching) + days-to-expiry, the
**max-pain** magnet strike, and a **dealer-gamma** read — *pinning* (vol-
suppressing) vs *amplifying* (vol-expanding) — with the call/put gamma walls
that bracket the expected range.

**What it is NOT:** a price target or a tradeable signal. It is a **statistical
tendency into expiration** under normal conditions — an earnings print,
guidance, M&A, or macro shock overwhelms dealer hedging entirely. For a
Minervini swing trader the honest use is: *a pin is a reason a breakout may
**stall** into expiry / a reason not to chase — confirm with the SEPA setup.*

Implementation: `backend/options/opex.py` (pure `classify_expiration` /
`max_pain` / `net_gex_and_walls` + `compute_opex` fetch),
`GET /options/opex/{symbol}`, `frontend/src/components/OpExPanel.tsx`.
Tests: `backend/tests/test_opex.py`, `frontend/src/lib/opex.test.ts`.
Reuses the same Massive options snapshot as `options/soir.py`.

---

## Max-pain (leads — gamma-agnostic, robust)

For the nearest expiry, over candidate settlement prices S (the listed strikes):

```
total_pain(S) = Σ_K call_OI[K]·max(0, S−K)·100  +  Σ_K put_OI[K]·max(0, K−S)·100
max_pain      = argmin_S total_pain(S)
```

The strike where the **least intrinsic value is owed to option holders** — the
price the dealer book is collectively incentivised to see at settlement. OI is
the only weight. A runner-up within 1% is flagged a **soft pin**; low strike-
count / low OI is surfaced so a thin grid isn't presented as authoritative.

## Dealer gamma (GEX) — read with the caveat

Per-strike, then netted over the expiry:

```
GEX_contract = sign · gamma · OI · 100 · spot² · 0.01      (sign: call=+1, put=−1)
net GEX      = Σ GEX_contract           # $ of dealer hedging flow per 1% move
```

- **Net GEX > 0 → dealers net long gamma → sell rips / buy dips → PINNING** (range-compressing). Price gravitates to the largest-gamma strike; the **call wall** (largest positive-gamma strike ≥ spot) caps the range, the **put wall** supports it.
- **Net GEX < 0 → AMPLIFYING** — dealer hedging feeds the move; breakouts run, flushes cascade.

### The sign rule is a heuristic — and the one thing to be careful about

The convention `call=+gamma, put=−gamma`, applied to **all** open interest, is
the blind **SqueezeMetrics / SpotGamma** rule. It assumes the dealer book
(unobservable) is long call-gamma / short put-gamma. The design review
(2026-06-26) flagged this as the #1 risk:

- It is **most defensible on index/ETF** (SPY/QQQ) and can **literally invert on
  single-name momentum leaders** — exactly the Minervini names this panel runs
  on, where customers are often net long calls. The panel therefore tags
  single names `single_name` and renders a **low-confidence ⚠️ caveat** on the
  gamma read; **max-pain is the more robust magnet** there.
- The sign is pinned with a code comment in `net_gex_and_walls` so it can't be
  silently flipped (a flipped sign inverts every pin/amplify verdict).
- **OI is end-of-prior-day** (OCC publishes overnight) — the pin reflects
  yesterday's book; today's fresh / 0DTE flow is invisible until tomorrow.
- When `greeks.gamma` is missing we fall back to Black-Scholes gamma from IV,
  and surface **OI coverage %** so a partial read isn't shown as complete.

## Expiration classification (no external calendar)

The 3rd Friday always falls on the 15th–21st. **Monthly** = 3rd-Friday;
**quad-witching** = 3rd-Friday in Mar/Jun/Sep/Dec (index futures + index options
+ stock options + single-stock futures all expire → strongest pin); everything
else = **weekly** (thinner OI, weaker/transient pin).

## Not wired (v1)

The **zero-gamma flip** level (the spot where net GEX crosses zero) needs a full
Black-Scholes reprice grid to be accurate; the cheap fixed-gamma approximation
the review rejected as imprecise. Deferred rather than shipped misleadingly.
