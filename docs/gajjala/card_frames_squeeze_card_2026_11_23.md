# 🎾 Reversal Squeeze cards as the 👀 Watch tile — the frames GET under `?card=squeeze` (2026-11-23)

Ajay 2026-11-23, verbatim: **"In the reversal squeeze can you make the charts same as in watch list please"**.

Spec `rswatch` §3.1-§3.4, work package `be-frames` (backend only). DISPLAY ONLY. UNMEASURED — a chart arrangement is not
a signal. Nothing rings, gates, sorts, sizes or trades differently.

## What is served

`GET /chart-maps/gajjala/frames/{symbol}?card=squeeze` (`card_frames.CARD_PARAM` = `card`, `CARD_SQUEEZE` = `squeeze`;
the FE twins `GGC_CARD_PARAM` / `GGC_CARD_SQUEEZE` are pinned equal by a source-read test).

- **Absent, empty or any other value** (`"watch"`, `"SQUEEZE"`, a padded word) → today's payload, byte for byte. No new
  key anywhere. Every other card, ⤢ and the small card ask without it.
- **Under `squeeze`** the payload is today's plus:
  - `card: "squeeze"` at the top level — the **echo**, on a `state: "ok"` payload only (never on `bad_symbol` / `error`);
  - `frames` in the Watch's served order, read off `gajjala_watch.constants.FRAMES` → 1m, 5m, 15m (`WATCH_ORDER`);
  - on every frame with bars: `tile.markers` = the frame's own 9/21 crosses over TODAY's bars
    (`tab.ema_cross_block` + `tab._on_bars` + `tab.EMA_CROSS_MARK` — the Watch tile's own lines), `ema_cross` = the
    block without `_`-keys (or null), `uptrend` = `{ok, short}` (K5 at the last bar through the Watch's reader
    `build.k5` over the frame's stored curves). A frame with no bars keeps `markers: []`, `ema_cross: null`, `uptrend: null`;
  - `held` stays null; no `run_bases` key;
  - the **5-minute frame**, when the GG5 doc holds the prior session's tail AND today has bars: `tile.bars / curves /
    vol_avg` = tail + today (`tab._tile_frame(doc, "5m", GG5, wide=True)`, the small card's reader) and `axis` = the
    **lead axis** below. `ema_blink`, `ema_tail`, `as_of_et`, `stale`, `source`, markers, `ema_cross`, `uptrend` are
    computed from TODAY's part exactly as on the default payload;
  - VWAP + zone bands: the existing overlay step, unchanged — VWAP is aligned by stamp, so it is null on every tail stamp.

**Why the echo.** The FE draws the Watch arrangement (1-min on top, 5-min + 15-min side by side) ONLY from a payload that
carries `card: "squeeze"`. An api that ignores the param (an old deploy, a proxy that strips the query) answers today's
payload → the 🎾 tile stays stacked 15 / 5 / 1. That is the safe side — never a wrong-order split.

**The 🚩 tab and the 🧪 Audited tab share this GET** (one shared card grid).

No new read, no fetch, no write: the tail is in the GG5 doc the GET already holds. A 2- / 3-tuple `stores` never calls
the on-demand 1-min builder (pinned).

## The lead axis — `gajjala_watch.build.lead_axis`

`lead_axis(ax, prior_bars, frame_min, *, from_et, to_et) -> (axis, None) | (None, reason)` — additive; the Watch never
calls it (its output is unchanged). `ax` = `build.axis(...)` of TODAY's bars. The card view passes
`from_et = GC.RS_TILE_PRIOR_FROM_ET`, `to_et = GC.RS_TILE_PRIOR_TO_ET` (the small card's window, read by name).

`(axis, None)` is a NEW dict = `ax` with:
- `lead` = the prior day's `[from_et, min(its extended close, to_et))` in `frame_min` slots (`alerts._closes` — 60 after a
  full day for 5-minute bars = `GC.RS_TILE_PRIOR_BARS_MAX`; 24 after a half day, to `HALF_DAY_AH_CLOSE`);
- `slots` = today's + `lead`; `x` = the prior slots (`(close − frame_min − from_et) / frame_min`, the rule `axis` uses)
  then today's slots + `lead`;
- `shade` = the prior day after its regular close as `ah` up to `lead` (the whole lead after a half day), then today's
  spans shifted by `lead`;
- `ticks` = ONE tick at slot 0 = the prior day ("Nov 20"), then today's ticks shifted by `lead` ("04:00" sits at `lead`);
- `start_epoch`, `frame_min`, `from_et`, `to_et` UNCHANGED — today's 04:00 grid, so a live print buckets exactly as before.

The ONE axis end of the three frames stays computed over TODAY's bars only (`BLD.axis_end(session, every_bar)`, one call
in `_build`): a prior after-hours bar never moves today's end (pinned).

### The nine refusal words (checks in this order; the first that fails names the reason)

| Case | Word (`build.py`) |
|---|---|
| `ax` is not a readable axis dict | `LEAD_DROP_NO_AXIS` = "no axis" |
| no prior bar | `LEAD_DROP_NO_PRIOR` = "no prior bar" |
| a prior bar is not a dict / has no readable stamp | `LEAD_DROP_JUNK_BAR` = "junk prior bar" |
| the prior bars span more than one date | `LEAD_DROP_TWO_DATES` = "prior bars span two dates" |
| that date's lead end is after today's 04:00 | `LEAD_DROP_NOT_BEFORE` = "prior day not before today" |
| `lead <= 0` | `LEAD_DROP_EMPTY` = "empty lead" |
| a prior slot < 0 or ≥ lead | `LEAD_DROP_SLOT` = "prior slot outside the lead" |
| the prior slots are not strictly increasing | `LEAD_DROP_ORDER` = "prior slots not increasing" |
| a today `x` entry is not an int | `LEAD_DROP_JUNK_X` = "junk today slot" |

All nine and `lead_axis` are in `build.__all__`. `build.py` writes no log line; never raises; never a partial axis.

## The drop line — `TAIL_DROP_LOG`

`card_frames.TAIL_DROP_LOG = "card_frames tail dropped %s %s: %s"` (symbol, frame, reason) — DEBUG, logger
`chart_maps.gajjala.card_frames`, the same pattern as `tab.CARD_AXIS_DROP_LOG`. ONE line per GET that drops a stored tail
that could NOT be laid; the frame is then today's, exactly the default one:
- today's bars are not the end of the stored wide frame → `TAIL_DROP_NOT_END`;
- `lead_axis` refused → its word verbatim (table above);
- any exception → `TAIL_DROP_FAULT` + the exception's class name (fail open, `state: "ok"`).

Silent by design (no line): not the 5-minute frame; no source doc; no axis; no bar today; no tail stored (a GG1 fallback,
an old doc). The EOD audit counts drops with `grep "card_frames tail dropped"` — it prints only where that logger's level
allows DEBUG (no log config is changed). A shown card re-asks once per board read (~5 min).

## Edges

- **K5 "—"**: K5 reads the frame's stored curves of TODAY's bars → `K5 —` until more than `GC.K5_SLOPE_BARS` bars of that
  frame closed today (15-min: until 05:00). The Watch reads its 2-session frame and answers earlier (HIS CALL 9).
- A tail exists only in GG5 docs written since 2026-11-08; a 5-min frame that fell back to GG1 or a name with no bar
  today serves today's frame (no tail).
- Under the board's 15-min toggle a 🎾 card carries no squeeze marks (FE side, the 11-08 rule).

## Tests

`backend/tests/test_gajjala_card_frames_squeeze_card_2026_11_23.py` — spec tests 1-15 (NEGATIVES named
`test_NEGATIVE_…`): default byte-identity for absent / junk params; order + echo; cross markers; ONE-engine equality
with `build.tile` on a real `bars.Frames`; K5 negatives + the slope constant read by name; the tail; the lead axis; the
nine refusals in table order + half day; tail negatives; VWAP null on tail stamps; today's end never moved; the route;
no write / no fetch; source guards; the drop line (one record per drop, zero for by-design cases).
