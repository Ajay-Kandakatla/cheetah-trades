# 👀 Watch — frames 1 / 5 / 15 and 📈 VWAP (2026-11-23, backend)

> **2026-11-27 — built, display only (frontend, branch `feat/watch-5m-grid-2026-11-27`).** The server still serves all three frames (`FRAMES` and `PUSH_FRAMES` unchanged); now Watch tiles and the Watch's ⤢ show the 5-min frame by default, and a frames menu ticks 1-min / 15-min back on. See [watch_5m_grid_2026_11_27.md](watch_5m_grid_2026_11_27.md).

Spec: `vwapzones` rev 2, package **be-watch**. The daily supply & demand zones are their own doc
(`watch_daily_zones_2026_11_23.md`); the FE side is `watch_vwap_zones_frontend_2026_11_23.md`.

## His words (2026-11-23 ~00:45–00:55 ET, in order)

1. "can you add vwap and supply demand zone in the daily time frame on the watch list please"
2. "I think we have 15 mins too"
3. "on the watch list I think we switch to 15 when candles are available for full chart"
4. "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board"
5. "Add vwap and supply demand too"

He was told GG does not use VWAP (S9 24:47); he asked for it anyway. **Display only — nothing gates, sorts, rings or caps
on any of this. UNMEASURED.**

## D-A — frames 1 / 5 / 15

- `C.FRAMES` = `1m`, `5m`, `15m` (served in that order; the board puts 1-min on top, the 5 + 15 pair under it; ⤢ is
  15 / 5 / 1 like the card view). Was 1 / 3 / 5 since 11-15.
- The 15-min chart costs **no extra fetch**: every frame is resampled from the same two raw 1-minute days
  (`bars.build_frames`; the loader is still called 2× per name per minute — pinned by a test before and after).
- Same 04:00 axis rule as 1m / 5m (and the card's 15-min chart): 48 slots to 16:00, 64 to 20:00, pre-market shaded to
  slot 22. Closed bars only (the settle rule); buckets on :00 / :15 / :30 / :45.
- **No push change**: `PUSH_FRAMES` stays `("1m",)`. "15m" IS on `alerts.FRAME_MINUTES` — only `PUSH_FRAMES` keeps a
  15-min cross silent (`not_push_frame`). Pinned; nobody adds "15m" to `PUSH_FRAMES` (HIS CALL #2).
- A frame with no closed bar yet serves words (`FRAME_NO_BARS_TEXT`), never a blank box. A frame missing from a stored doc
  (every live doc right after the deploy holds 1m / 3m / 5m) serves `FRAME_PENDING_TEXT` (in / out of the window). A stored
  "3m" is never served. The build child (`--build`) rebuilds a listed doc lacking a tf of `C.FRAMES`; `--new-only` does not.
- `cross_alerts.py`: docstring word only (3- and 5- → 5- and 15-minute); its code is pinned equal to main's (AST digest).
  `bars.RULE_OF["3m"]` stays (nothing builds it).

## D-C — 📈 VWAP

- THE engine: `daytrading.indicators.vwap_session` (Σ typical × volume / Σ volume, reset per ET date). The new
  `gajjala_watch/vwap.py` holds **no formula** — it only chooses the rows: today's raw 1-minute rows of the sessions named
  by ONE constant, `C.VWAP_SESSIONS`.
- Computed ONCE per name per build (`build.name_vwap`), stored per frame as `vwap.values` aligned to the bars: the value at
  a bar = the minute VWAP after the last 1-minute bar inside its bucket. Served as the third curve (tone `vwap`, label
  `VWAP`) after the two EMAs. The line ends at the last closed bar — the live candle does not move it.
- It runs inside the tile build, AFTER the cross push (`loop.py` runs `XA.run` first) — nothing here can delay a ring.
- Never NaN: a stored NaN is served as None; a ragged / all-None / junk stored list serves no curve.

### The three anchors (HIS CALL #1 — BLOCKING; all three built behind ONE constant)

| `C.VWAP_SESSIONS` | 04:00–09:30 | 09:30 → regular close | after the regular close |
|---|---|---|---|
| `("rth",)` — **default** (= `vwap_session`'s own default argument) | no VWAP drawn | from 09:30 | none (stops at the close) |
| `("premarket", "rth")` | from 04:00 | carries the premarket volume | none (stops at the close) |
| `("premarket", "rth", "afterhours")` | from 04:00 | carries the premarket volume | runs through after-hours |

The default draws NO VWAP 04:00–09:30 on charts that open at 04:00 and differs from a thinkorswim VWAP with extended hours
on. Any other value (a str, `()`, an unknown session) → VWAP off, ONE warning, never a raise; `rules_line()` = "".

### Half days [C2]

The house session tag has no half-day clock (rth = 09:30–16:00 by the clock). The wrapper cuts on the MINUTE series: a row
tagged "rth" whose bar START is at or after the session's REGULAR close (`alerts._closes` — 13:00 on 2026-11-27) counts
as after-hours. So on 1m / 5m / 15m (and the card view, which reads the stored values) every label after 13:00 is None
and the 13:00 label is finite; the same raw on a full day runs to the 16:00 label. Pinned by unit tests; first live look
2026-11-27 after 13:05 ET.

## The words (one sentence, three surfaces)

`vwap.rules_line()` = the legend hover = ℹ️ (`info.vwap_text`) = the rules-panel clause (be-zones wires the panel). Every
number is filled from a constant by name (`daytrading.data` opens, `C.TAB_LABEL`, `C.FRAME_WORDS[C.AXIS_FRAME]`); no
digit is typed (ast test). Legend label: `VWAP (from 09:30 ET)` under the default.

## Loop hooks [C1]

- `run_iteration` is untouched (a source test pins it never names the zones).
- `--loop` starts the levels module's daemon thread (`_levels(thread=True)`) before the slot's iterations.
- `--build` (`build_all`): `build_pending` → `_levels(first=built)` rounds with ONE shared `tried` set, ending on the list
  re-read. A name added while the zones are read is built by the same child; a `no_prints` / `failed` name is fetched
  once per child however many rounds run (a test fails fast if it ever loops). Nothing to build and nothing read → ONE
  `build_pending` call, as before. When a round built nothing and has no rest pass, `_levels` is skipped (it would read
  nothing) so the list re-read is literally the last call.
- `_levels` imports `C.LEVELS_MODULE` lazily, is fenced (any fault → 0, one log line), is never called on `--dry-run`.

## Cost (host venv, `python -m scripts.gajjala_watch_build_cost`, 36 synthetic names, clock 15:59:50, best of 3)

| shape | median ms / name | Δ ms | total s (36 names) |
|---|---|---|---|
| main 1/3/5, VWAP off | 57.9 | 0.0 | 2.091 |
| new 1/5/15, VWAP `rth` (default) | 71.1 | +13.2 | 2.565 |
| new 1/5/15, VWAP `premarket+rth` | 84.2 | +26.3 | 3.030 |
| new 1/5/15, VWAP whole day | 84.3 | +26.4 | 3.049 |

Live reference: the 2026-11-20 state doc read `wall_s` 4.531 s for 29 names (fetch included). The default adds ≈ 0.4 s
per 29-name minute, after the cross push. Re-measure on the first live session (`wall_s`, `bars.failed`).

## Fixture

`python -m scripts.gajjala_watch_fixture_2026_11_23 --write` → `frontend/src/components/__fixtures__/gajjala_watch_board_2026_11_23.json`
(deterministic; the real `payload.build` over synthetic minutes + stored `levels` docs from the real zone engine). Rows:
ZONE (> $1, zones in range), PENNY (< $1, a `lo == hi` band in range), RETRY (state retry), OLDDOC (an old 1m/3m/5m doc).
The 🎯 / 🏷️ / 🔢 / 🚫 / 🗂 sidecars are served as their fault values (they read other stores).

## Tests

`backend/tests/test_gajjala_watch_frames_1_5_15_2026_11_23.py` (step-0 goldens digested on main 7b618467 before any
edit: the 1m cross push, the served 1m / 5m blocks, the 📶 5m block — byte-equal) ·
`backend/tests/test_gajjala_watch_vwap_2026_11_23.py`.

## HIS CALL

1. **BLOCKING** — the VWAP anchor (table above); default `("rth",)`.
2. `PUSH_FRAMES`: 5-min / 15-min crosses stay drawn only.
5. 15-min chart = today's bars from 04:00 (there is no "switch to 15") — or prior-session 15-min candles so it is full at
   the open.
6. ⤢ order 15 / 5 / 1 (he listed 1 / 5 / 15).
7. The VWAP tip waits for the closed bar — or move it live from prints (another definition).
15. The contracts "HARD KEEP" re-pinned to 1 / 5 / 15 (main session).
16. The one-shot `--build` so the 15-min charts show before 04:00.

## 2026-11-23 evening — 📈 VWAP over all hours (HIS CALL #1 answered)

Ajay, verbatim (~21:30 ET): "Why is VWAP not showing up in AH?" · then, told it was regular-hours only and offered the
full-day option: "Please extend them to all hours..".

**The change:** `chart_maps/gajjala_watch/constants.py` `VWAP_SESSIONS = ("premarket", "rth", "afterhours")` —
`vwap.SESSION_SETS[2]`, the third anchor already built. One constant; the 👀 Watch tiles (1 / 5 / 15) and the card frames
(they read the same constant through `WC.VWAP_*`) both follow. No formula changed: the same engine
(`daytrading.indicators.vwap_session`) over today's 1-minute rows.

**What the number now means:** the volume-weighted average price of TODAY from the 04:00 ET premarket open
(`daytrading.data.ET_PREMARKET_OPEN`) through the last closed bar, after-hours included (to 20:00 ET; 17:00 on a half
day). Yesterday's bars — its after-hours included — never count; neither does a row the house tagger calls `closed`
(before 04:00, from 20:00). **It differs from a broker's regular-hours VWAP all day** (Fidelity / thinkorswim default
to 09:30 → 16:00), because premarket volume counts from 04:00; on a gapper with heavy premarket prints the gap is large.
After the regular close the line keeps moving with every after-hours print.

**Half day (2026-11-27):** the regular-close cut (`alerts._closes`, 13:00) only re-tags 13:00–16:59 rows as after-hours;
under the whole-extended set they are counted, so the line runs to the last closed bar (17:00 close). The cut still
stops the line at 13:00 if the constant goes back to `("rth",)`.

**Served words** (filled from the constants, no digit typed): legend "VWAP (from 04:00 ET)"; ℹ️ / hover / rules panel
"… the whole extended session, premarket and after-hours included from 04:00 ET … runs through after-hours …". The FE
prints the served text only. FE fixture regenerated (`--write`): only the VWAP words + curve values moved.

**Tests:** `backend/tests/test_gajjala_watch_vwap_all_hours_2026_11_23.py` (new — 04:00 → last closed bar on every frame,
the hand sum, a heavy 04:00 print and a heavy 17:00 print move the line; NEGATIVES: yesterday's after-hours never
counts, `closed` rows never count, under the rth set the same prints change nothing, junk constants draw nothing and
never raise) · `backend/tests/test_gajjala_watch_vwap_2026_11_23.py` re-pinned (old-default tests now run under an
explicit `("rth",)`; O1 pins `C.VWAP_SESSIONS == VW.SESSION_SETS[2]`). Display only: nothing gates, sorts or rings on it.
