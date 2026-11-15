# 🔀 ➖ Horizontal Fade: 9 / 21 EMA cross, marked on the card and pushed (2026-11-15)

## His words

> "I like how you put the 9 EMA and 21 ema cross over for OMH can you add an alert in horizonal fade when that happens?"
>
> "For any stocks that crossing over and add the same feedback in to that horizontal fade charts"

Context: in the replay videos (`eod-audits/replays/`), OMH (Horizontal Fade, 2026-11-09/10) showed the 9 EMA crossing above
the 21 EMA before the run.

## What was built

**One engine: `backend/chart_maps/gajjala/ema_cross.py`.** It is pure, uses closed bars only, and does not depend on the ➖ sub or on any timeframe. The ➖ card and the ➖ push both call it. The planned Gajjala Watch dashboard (1, 3 and 5-minute charts) can reuse it as is.

| API | What it does |
|---|---|
| `crosses(bars, fast=None, slow=None, *, start=0, through=None)` | `bars` = closed bars oldest first, `{"t": "YYYY-MM-DD HH:MM" (bar close, ET), "c": close}`. Computes the house EMA over all bars (`orderflow.signals.ema` through `bars._masked_ema`, so warm-up stays a gap). The spans default to `EMA_FAST` / `EMA_SLOW` (9 / 21). Judges crosses from index `start`. `through` drops every bar stamped after it, so a live bar is never judged. |
| `crosses_from_emas(ema_fast, ema_slow, ts, closes=None, idx=None)` | The core over EMA series that are already computed and aligned by index (a Frame's `ema9`/`ema21`, a card's curves). |
| `frame_crosses(F)` | A `bars.Frame`'s bars for today, using its own `ema9` / `ema21`. The prior session's last bar can serve as the "prior bar". |
| `session_crosses(xs, session)` / `latest_up_cross(xs, session=None)` | Keeps one ET session's crosses / returns the last UP cross. |
| `finite(x)` | The finite-number read (None / NaN / inf / bool count as unknown). |

Each cross = `{"i", "ts", "dir": "up"|"down", "ema_fast", "ema_slow", "close"}`.

**The rule** (bar i and bar i−1 both closed, all four EMA values finite):

- **up:** 9 > 21 on bar i, and 9 ≤ 21 on bar i−1.
- **down:** 9 < 21 on bar i, and 9 ≥ 21 on bar i−1.

No new number. The spans are the existing `EMA_FAST` / `EMA_SLOW`.

**Card** (`tab.ema_cross_block`, called from `setup_tile` for every setup in `constants.FADE_CROSS_SETUPS` = `("horizontal_fade",)`):

- Reads the drawn frame's own served 9 / 21 curves, which are the pass's EMA values.
- Serves one marker per cross of the session: kind `ema_cross_up` (green diamond) or `ema_cross_dn` (red diamond). The marker sits on the 9 EMA value, with the served sentence as its tooltip.
- Serves `gajjala.ema_cross = {tf, dir, text, crosses[]}`. The latest cross is printed under the chart as one line, e.g. "🔀 9 EMA crossed above 21 EMA at 10:20 ET", or "… crossed under …" in red.
- No cross → no key and no marker.
- This applies on all three Gajjala tabs (🚩, 1-minute, 🧪) and on a ➖ card shown under 🧠.

**Push** (`alerts.run_fade_cross`, GG5 only; it runs as a step of the 5-minute cron pass and of the ⏱ bar-close child through `run._cron_deps().fade_cross`). It rings when a ➖ name with a card (state in `tab.TILE_STATES`) has its latest UP cross today on the card's own frame (the read's frame, 15m first), and all of these hold:

- that cross bar is the frame's latest closed bar, and it is fresh (the A+ freshness clock);
- the market is open (closed-day gate);
- the bar is inside the A+ push window: after 09:45 ET, until the extended close, never pre-market;
- the session volume is at or above GG's 1M floor (`K11_MIN_SESSION_VOLUME`); unknown volume holds the push.

Delivery:

- **Once per name per session.** An insert-only claim `GGX:{date}|{SYM}|horizontal_fade` lands in `gajjala_alerts` **before** the send. Its states are `cross_claimed` / `cross_pushed` / `cross_no_target` / `cross_failed`, never `shadow`/`pushed`, so the 🏁 Track record never reads it as an A+.
- **Owner-scoped**, on the existing `gajjala_potential` kind (`constants.FADE_CROSS_PUSH_KIND = POTENTIAL_PUSH_KIND`, the ⚡ break precedent). No new OWNER_KEEP_SET kind.
- **The body** is "9 EMA crossed above 21 EMA on the 5m bar closing HH:MM ET · close X · UNMEASURED — information only, not an entry". The word "buy" never appears.
- **Mode switch:** `constants.FADE_CROSS_PUSH_MODE = "live"`. `"off"` is one word away, and any other value counts as off.
- The 📲 Notifications page shows it under the 🧠 kind's toggle.

**ℹ️ Rules panel:** one clause in the 🚩 section note (`alerts.fade_cross_rules_line`, built from the constants).

## What does NOT ring

- a cross under (9 below 21): it is marked on the card, never pushed;
- a second up cross the same session (claim);
- a cross on the bar still printing (the frames hold closed bars only);
- an older cross first seen later (late);
- a cross bar that starts before 09:45 ET (pre-market or his first 15 minutes) or after the extended close;
- a closed day;
- a name under 1M session volume, or with unknown volume;
- any setup other than ➖, or a ➖ read with no card;
- the 1-minute page and the 🧪 tab (their cards get marks, but never a push);
- a dry pass and the on-open pass.

Nothing about the A+ gate, any detector rule, threshold or sort changed.

## Goldens moved (additive only, leaf diff checked: 0 changed, 0 removed)

- `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json`: 60 leaves added (`gajjala.ema_cross` + one `ema_cross_up` marker on the 2 ➖ tiles and the ➖ 🧠 tile, live + shadow). WRITES golden byte-identical.
- `frontend/src/components/__fixtures__/gajjala_1m_board_2026_10_27.json`: 10 leaves added (🧠 sub, GGA ➖ tile).
- `frontend/src/components/__fixtures__/gajjala_on_open_golden_2026_10_15.json`: 10 leaves added (same).

Potential, track-record and Luk goldens did not move.

## HIS CALLs (open)

1. **Bearish cross push?** Today a cross under is only marked on the card. Should it also ring?
2. **Other subs?** `FADE_CROSS_SETUPS` = ➖ only. Should it cover 💋 / 🚩 / 🌀 / 🎾 or 🧠 names too?
3. **Pre-market crosses.** The push uses the A+ window, so a cross before 09:45 ET does not ring. If the OMH cross came before the open, it would have been marked on the card but not pushed. Should it use the 🧠 window (04:00–20:00, with 09:30–09:45 muted) instead?
4. **Which frame.** The push uses the card's own frame (the ➖ read's frame, usually 15m). Should a cross on the other frame (5m) ring too?
5. **The 1M floor** is applied, the same floor every Gajjala push keeps (and the ⚡ break push uses). Drop it for this information push?
6. **The 1-minute page:** should it get its own cross push (its own kind / mode)?
7. **UNMEASURED.** No study says a 9-over-21 cross on a fade name leads to a run. It is shown as information only.
