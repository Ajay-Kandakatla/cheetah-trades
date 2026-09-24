# The moving averages reach the Support tab's own frames (2026-09-24)

> "I would need 9EMA and 20 SMA here too as check boxes"
>
> — Ajay, on a screenshot of the Support tab's LEDGER row

The Chart Maps tiles got the three averages on 2026-09-23. This tab builds its
**own** tiles in `chart_maps/support.py`, so they never reached it — the gap I
flagged as his call the day before, now closed.

All three ship, not two. The overlay checkboxes are **shared state** across every
chart surface (`cm-hidden-overlays-v2`), and `presentGroups` only draws a box for
a family the payload actually carries — so a tab serving two of the three would
make the 200 box appear and disappear as he moved between surfaces. The 200 is
simply absent wherever the frame is too short for it, which on this tab's
intraday frames is most of them.

## No frontend change at all

`SupportLevels.tsx` already runs `presentGroups` → `OverlayLegend` → `filterTile`
→ `PatternChart`, the same pipeline the tile boards use. The three checkboxes
appear in the LEDGER row the moment the payload carries the curves. The entire
change is backend.

## The two things that can silently go wrong

### 1. The key — and it fails *silently*

`board._ma_curves` joins the average series to the drawn bars **by string**.

| frame | how its bars are stamped |
|---|---|
| daily | `2026-09-23` — `board._row_date` |
| intraday | `2026-09-23 10:25` in **ET** — `support._frame_bars` |

Hand an intraday frame the date-only default and nothing raises. The join
matches nothing, every column comes back all-`None`, every curve is dropped as
all-warm-up, and the averages **silently never appear on a 5-minute chart**.
Measured before the fix: `curves = 0`.

So `_ma_series` and `_ma_curves` gained an optional `stamp`, and
`support._intraday_stamp` is now the single definition of that format —
`_frame_bars` calls it too, so the two cannot drift. The bug is kept as a test
(`test_NEGATIVE_the_board_default_key_draws_NOTHING_intraday`): if it ever
starts producing curves, the stamps converged and the branch can go.

### 2. The frame — full, then trimmed

Daily takes the **untailed** frame out of `bars_for(frame_out=...)`, so a 200 SMA
under a 1-year chart is a true 200-bar average and does not move when he changes
the Zoom. Verified: a 120-bar view off a 300-bar frame serves 29.95 where the
mean of the 120 visible closes is 33.95 — it reached past the window, as it must.

Intraday takes `chart_df`, the widest frame that timeframe has.

## The inherited rule: an intraday average is in its own bars

A 20 SMA on the 15-minute chart is **twenty 15-minute bars**, not twenty days
painted under a 15-minute label. That is the rule this tab's *levels* have
followed since 2026-09-23, and the averages must not differ from it — the
alternative is the 2026-08-29 "why is one hour showing Monthly?" bug in a new
costume.

## Tests

`backend/tests/test_support_moving_averages_2026_09_24.py` — 19.

**Three of the first four mutations SURVIVED, and that is the story of this
file.** The original tests all handed `_attach_ma` a frame directly, so:

| mutation | first pass | after |
|---|---|---|
| intraday uses the date-only key | caught | caught |
| daily loses the untailed frame | **survived** | caught |
| `bars_for` stops filling the out-list | — | caught |
| EMA warm-up mask deleted | **survived** | caught |
| the stamp format drifts | **survived** | caught |
| the ET conversion is dropped | — | caught |

What was wrong with each:

* **The wiring was untested.** Every test called `_attach_ma(tile, df)` itself,
  so none of them noticed when the tile builder stopped passing a full frame.
  Two source guards now pin `frame_out=_ma_frame` and the handoff.
* **The warm-up test asserted on the 20 SMA**, whose warm-up pandas gives for
  free (`rolling(20)` needs 20 observations) — it was asserting on pandas. The
  mask only matters for the **EMA**, which `ewm(adjust=False)` emits from bar
  one. Now asserted on the 9.
* **The stamper test was a tautology.** It compared `_frame_bars` output to
  `_intraday_stamp` *after* making the first call the second. The format itself
  is now pinned against a known timestamp (13:30 UTC → `2026-09-22 09:30` ET,
  the opening print), which also catches a dropped timezone conversion.

## Not in this change

The **bullish read** he asked for next ("I am looking for bullish 9EMA and 20
SMA") is not here. He declined to let me define it — *"Research please there are
videos on youtube and look other places.. lot of people use it for intraday"* —
so the definition is being researched from sources and comes back to him as a
proposal, not a shipped rule (Rule #1). These lines are drawings: they sort
nothing, gate nothing and alert on nothing.

The existing `Trend on this timeframe` line is untouched — it reads EMA20 and
EMA50, a different pair from his, and nothing here changes it.
