# Study overlays — AMD, Fibonacci, mean reversion (2026-09-12)

Ajay: *"Can you build two things in your existing charts? I wanna be able to
toggle AMD ... and Fibonacci ... Default toggle on only supple demand and order
block for me."* Then *"Also mean reversion please on 1 year charts"* and
*"Basically any chart time frame add this newly please."*

Asked which conventions he meant, he chose **both** AMD variants, a
**last-major-swing** fib anchor with **retracements + extensions**, drawn on the
**expanded chart only**.

## The honesty line, first

**All three are uncited chart conventions, none has been measured forward, and
none gates anything.** No scan reads them, no alert fires from them, no lane
buys on them. Each module carries `CITED = False` and a `SOURCE_NOTE`, and the
payload ships a `studies.note` so the caveat reaches the screen rather than
living in a docstring.

For scale: the app already measured this family's nearest relative — the ICT
tab came back at **+0.03R over 6,004 signals against placebo** (2026-09-04).

## The four modules

| Module | What it draws |
|---|---|
| `supply_demand/amd.py` | daily swing AMD: base → stop-raid → markup |
| `daytrading/amd_sessions.py` | intraday session AMD |
| `supply_demand/fib.py` | 0.382 / 0.5 / 0.618 / 0.786 + 1.272 / 1.618 |
| `supply_demand/meanrev.py` | least-squares channel ±1σ / ±2σ |
| `supply_demand/keltner.py` | EMA20 ± 2×ATR10, plus the TTM squeeze |

### AMD — the whole test is the close

A raid trades **through** the base edge and **closes back inside it**. A close
beyond the edge is a *breakout* and means the opposite thing. Same rule as
`smc.liquidity_sweeps`, deliberately — one definition of "swept" in the app.
Both modules emit `amd_accumulation` bands and `amd`-toned lines, so **one
checkbox governs both**.

### Session AMD deviates from canonical ICT, on purpose

Canonical AMD uses the **Asian range, 19:00–00:00 ET**. **The app cannot see
it** — `daytrading/data.py` caches 04:00–20:00 ET and tags the rest `closed`.
Drawing a 3am range from bars that do not exist would be an invention, so
accumulation is the **04:00–08:00 ET** consolidation and `WINDOW_NOTE` says so
in the payload.

### Fibonacci

Anchored on `smc.swing_points` — the same pivot detector behind BOS/CHoCH, so a
fib level cannot disagree with the structure line next to it. A leg must clear
`MIN_LEG_ATR` or nothing is drawn; without that floor a four-bar wiggle becomes
the anchor and the levels move every session.

```
retracement r:  price = B - r * (B - A)      r=0 is B, r=1 is A
extension   e:  price = A + e * (B - A)      e>1 is beyond B
```

**0.5 is not a Fibonacci ratio** and 1.272 is √1.618. Both are labelled
convention rather than presented as maths.

### Mean reversion is SLOPED, and that was my call

He did not pick a construction. A **flat** mean marks every leader "rich" for
its entire run — measured on the fixture, a steady ramp sits **~1.7σ** above a
flat average against **~0** for the fit that removes the drift. An overlay
permanently red on exactly the stocks the app exists to find is worse than no
overlay. `SLOPED = False` flips it.

σ is dispersion about the fit, **not a probability** — the fit is estimated on
the same bars it scores.

### Keltner is an overlay, not a tab

He asked for *"the Keltner channel strategy a new tab"*, then chose otherwise:
*"Over lay I think is better to toggle off if I want to."*

**There are three Keltner "strategies" and they trade opposite ways** —
band-fade, trend-pullback, squeeze-breakout. An overlay does not have to pick:
it draws the channel all three read, and labels the one state not visible by
eye, the squeeze. Band-fade is deliberately not modelled as a signal — it would
duplicate `meanrev.py`, shipped the same day, and neither is measured.

```
mid = EMA(close, 20);  upper/lower = mid ± 2.0 × ATR(10)
squeeze = Bollinger(20, 2.0) sits INSIDE Keltner(1.5)
```

`SQUEEZE_MULT = 1.5` is deliberately **tighter** than the drawn `MULT = 2.0`
(Carter's construction). Collapsing them would report a squeeze far too often.

**A squeeze is compression, not direction.** `reading()` says so in every
payload, and carries no `direction`, `bias` or `signal` key at all — the word
reads like a signal and is not one. Pinned by
`test_the_squeeze_NEVER_claims_a_direction`.

`position` runs **outside [0, 1]** when price leaves the channel; clamping
would hide exactly the case the overlay exists to show.

## Where it is computed, and why only on request

One call site: `chart_maps/board._attach_studies`, after the tab dispatcher.
Twelve tile builders, one definition — no tab can end up with a different fib
from its neighbour.

`studies=False` by default. **Not primarily for speed:** every tab's tile
contract asserts the exact bands it produces, and silently appending an uncited
band to all of them would have weakened **seven real tests** into "contains at
least". The frontend asks for them only while one of the three checkboxes is on.

## The default flip

`chartOverlays.DEFAULT_ON = ['demand', 'supply', 'order_block']` — his ask,
verbatim. The localStorage key is **bumped to `cm-hidden-overlays-v2`**: reading
v1 would hand every existing browser its old empty hidden-set, i.e. the previous
show-everything default, and his instruction would silently never take effect.

The three study families set `always: true` so their checkbox renders even with
no data in the payload — otherwise the switch that turns them on could never be
reached, because they are off.

Fib is stripped from grid tiles by `filterForGrid` and kept on the expanded
chart, which is what he chose.

## What the tests do and do NOT protect

26 tests in `backend/tests/test_chart_studies.py`, 9 of 10 mutations caught:
raid accepting an outside close, fib size floor, fib extensions computed as
retracements, fib borrowing a trade tone, flat-vs-sloped, the σ floor, NaN
closes, the Asian-range caveat, and a two-sided raid inventing a direction.

**Read this before tightening `find_base`.** The tightness statistic —
window-local median true range — is **reasoned, not verified**. Mutation-tested
2026-09-12: swapping the median for the mean, and window-local for whole-frame
ATR, each produced the **identical** base on every fixture. An outlier bar
widens the range and the denominator together, so the ratio barely moves. Both
choices are kept as the more defensible constructions, not because a test
distinguishes them. **The suite will not tell you if you get this wrong.**

A related correction worth recording: an earlier version of this work claimed
whole-frame ATR was the cause of a "base swallows its own raid" bug. It was
not. That symptom came from a malformed test fixture whose raid bar closed
*below* the base — an accepted break, which the code correctly rejected.
