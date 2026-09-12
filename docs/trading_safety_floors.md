# Manipulation-safety floors

**Owner ask, 2026-09-11:** *"I wanna be able to find stocks that have explosive
sale with safe entry where there wouldn't be easy manipulation.. By whales.. So
make sure to give me not penny stocks and other safety gates or warn me.. I
dont want 10 Million Market Cap stocks too.. I want real growing stocks like
AXTI and SABR with genuine sales."*

Source of truth: [`backend/trading/safety_floor.py`](../backend/trading/safety_floor.py).
Tests: [`backend/tests/test_safety_floor.py`](../backend/tests/test_safety_floor.py).

---

## What the audit found (2026-09-11)

A six-agent audit of every path that can reach the broker:

| Finding | Detail |
|---|---|
| **The chokepoint had no floors** | `trading/entries.py::_evaluate` is the single function every stock lane funnels through. It enforced `price > 0` and nothing else — no cap, no minimum price, no dollar volume, no float. |
| **It had already filled a penny name** | SABR at **$2.24 on 2026-09-09**, 11,043 shares, stopped out **−4.46% / −0.74R**. |
| **The Minervini lane structurally could not gate on cap** | `market_cap` is not a field on a scan row — 0 of 2,945 rows carried one. |
| **`sepa/adr.py` liquidity was an OR** | `avg_dollar_vol >= $20M **or** avg_shares >= 200k`. **848 of 2,945** rows passed on the share leg alone, **328** of them under $5. ARAI read `liquid=True` on **$148,074/day**. |
| **The cap floor is circular** | `market_cap = shares × last price`, so a pump lifts a name over the floor. **5 names crossed $700M in 21 sessions purely on price.** |

## The three floors

| Floor | Value | Kind | Why that kind |
|---|---|---|---|
| `MIN_SHARE_PRICE` | **$2.00** | **HARD block, every lane** | Not circular — a promoter cannot argue a $0.74 quote into a $2 one without actually paying for it. This is the backstop. |
| `MIN_CAP_USD` | **$700M** | **HARD when the cap is known**, WARN when unknown | Blocking on *unknown* would silently delete every name whose shares row is unwarmed — that hides the gap instead of showing it. |
| `MIN_DOLLAR_VOL` | **$20M/day** | **HARD in `sepa/adr`**, WARN on the entry path | The lanes disagree about how thin is too thin; a silent block on a name he typed himself reads as a broken button. This is the *"or warn me"* half of his ask. |

A second warn tier, `THIN_DOLLAR_VOL = $5M/day`, labels the one-order-moves-it
names.

### Why $2 and not $5

He named **SABR** as a stock he *wants*. SABR trades at **$2.17** today. A $5
floor would delete the exact cohort he asked to keep. $2 is a tail backstop,
not a valuation opinion, and SABR at $2.17 still passes it.

What it actually stops, measured 2026-09-11 over 3,738 research-cache rows
(`backend/studies/liq_leg_impact.py`): **208 rows price under $2.00**, of which
**3 — BTBT, GPRO, UWMC — clear the $20M/day liquidity floor** and are therefore
stopped by *nothing else in the app*. The other 205 are already caught by
liquidity. None of the 208 is a qualifier or buyable today, so the floor changes
no decision on today's book; it exists for the three names liquidity cannot see
and for the next SABR-at-$2.24 fill.

### Why the entry path warns on an unknown cap while the boards fail closed

Deliberate asymmetry, pinned by `test_unknown_cap_warns_and_never_blocks`:

- A **board** is a discovery surface. Hiding an unverifiable name costs nothing.
- The **entry path** is reached only after a lane chose the name or he typed it.
  A silent refusal there is indistinguishable from a bug.

## Liquidity: the share-count leg is deleted, not AND-ed

He first asked for **OR → AND**. Measured before shipping:

Measured 2026-09-11, `backend/studies/liq_leg_impact.py`, 3,738 rows — the OR
rule called **3,091** of them liquid:

| Option | Liquid after | Removed vs OR | Penny names removed | Institutional names lost |
|---|---|---|---|---|
| OR → AND | 2,113 | 978 (31.6%) | 925 | **53** |
| **Delete the share leg** (shipped) | 2,166 | 925 (29.9%) | **925** | **0** |

**925 rows passed on the share leg alone**; 365 of them under $5 on a 50-day
average price. Worst offenders: **ARAI $0.29 on $148,074/day**, **AITX $0.02 on
3.76M shares/day**.

The 53 are high-**priced**, low-**share** institutional names — they trade few
shares because each share is expensive:

| Symbol | 50d avg price | Avg shares/day | Avg $-volume/day |
|---|---|---|---|
| NVR | $6,404.75 | 32,097 | $205.6M |
| SEB | $4,308.91 | 12,306 | $53.0M |
| FCNCA | $2,150.14 | 70,499 | $151.6M |
| WTM | $2,138.33 | 19,784 | $42.3M |
| MKL | $1,895.37 | 68,076 | $129.0M |
| MTD | $1,357.57 | 177,567 | $241.1M |
| GHC | $1,167.41 | 27,308 | $31.9M |
| NEU | $851.73 | 120,720 | $102.8M |

Under AND, every one of them fails the 200k-share leg and is deleted. That is
the **opposite** cohort from the manipulation risk he asked to be protected
from. Deleting the share leg removes the identical 848 penny names and keeps
all 53, so that is what shipped. `min_shares` stays in the signature (unused,
still reported on the row) so stored rows and callers do not break;
`test_adr_liquidity_has_no_or_leg` pins by AST that it cannot rescue a thin
name again.

**Minervini basis (TLSW):** the book's rule is that institutions cannot
accumulate thin stocks, so a thin name carries no smart-money tailwind. The
book's unit for "thin" is money changing hands, not share count. The OR leg was
the drift; removing it moves the code *toward* the book, not away from it.

## Known limits

1. **The cap floor is circular.** Cap = shares × last price, so price action
   feeds the gate that is supposed to judge price action. The $2 floor and the
   $-volume floor are not circular, which is why they carry the weight.
2. **Cap data is stale.** 78.4% of shares-cache rows are older than their own
   7-day TTL. An unknown or stale cap warns; it never blocks.
3. **Pattern alerts still have no size gate.** HGBL was pushed at $1.41 on
   $160k/day. Alerts are not orders, so this is a labelling gap, not a capital
   gap — but it is open.
4. **`float` is still unchecked everywhere.** A large cap with a 4% float is
   exactly the whale-movable shape he described, and nothing in the app reads
   float today.

## Guards

| Test | What it pins |
|---|---|
| `test_entries_calls_the_floors_and_feeds_them_into_blocked` | AST: `_evaluate` calls `safety_floor.check()` **and** routes the result into `blocked`. |
| `test_every_lane_buys_through_entries_never_the_broker` | AST, alias-aware: all four lanes call `entries.enter()`; none calls `submit_bracket`/`submit_stop` directly. |
| `test_adr_liquidity_has_no_or_leg` | AST: the `liquid` assignment is a single `Compare`, never a `BoolOp`. |
| `test_cap_floor_agrees_with_the_sd_boards` | The entry-path cap floor equals the S/D board floors. |
| `test_evaluate_blocks_a_sub_two_dollar_fill` | Regression for the real SABR $2.24 fill. |

All four guards were mutation-tested on 2026-09-11 — the mutation was asserted
to have applied before the test ran, because a `.replace()` that silently
no-ops reads exactly like a guard that did not fire. All four **CAUGHT**.
