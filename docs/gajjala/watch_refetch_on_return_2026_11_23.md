# 👀 Watch — one board GET on return to the tab (2026-11-23, frontend)

Spec: `ggconn` rev 2 §3.2, package **wp2-refetch-on-return**. **TRANSPORT / DISPLAY ONLY — no rule, gate, ring
condition or push changes. UNMEASURED.**

**This does NOT fix the delay he saw on AKAN.** That delay is the live feed going blind (28.8 % of the 11-23 window,
spec §1.1 / §1.5); the socket policy is HIS CALL #10–#12 and untouched here. This package only closes one REST gap.

## His words (2026-11-23 ~12:00 ET)

"Can you clean up some connection I am seeing delays price update for AKAN on the watch chart.." and "I would like us
to focus on connections of Gajjala more for the rest of the tabs."

## What changed

- Before: the board's minute chain (`armMain`) skips a tick while the tab is hidden and re-arms a FULL served
  `refresh_sec`. Back on the tab, the bars could be up to one extra cadence old before the next GET.
- Now: back to the tab (`visibilitychange`, visible) with the last full GET **issued** at least one served
  `refresh_sec` ago → ONE full board GET at once. Its landing re-arms the chain through the existing `armMain`
  calls, so the next GET is one `refresh_sec` after that landing.
- The rule is ONE pure function, `frontend/src/lib/ggwReturn.ts` `ggwReturnRefetch({hidden, refreshSec,
  lastIssuedMs, nowMs})`: false while hidden or when `refreshSec <= 0` (out of window); else
  `nowMs - lastIssuedMs >= refreshSec * 1000`. It types no number — `refreshSec` is the served `refresh_sec`.
- The board keeps ONE ref, `fullAt`, stamped inside `loadAll` right after `++loadSeq.current` — at ISSUE, never at a
  landing. One `visibilitychange` effect calls `clearMain()` then `loadAllRef.current()`.

## [C9] why there is no "in flight" input

`getJson` has no timeout and no abort. A GET that died while the tab was hidden would block the return forever if a
busy flag guarded it. The age test alone answers both cases:

- a GET in flight and younger than one cadence → no second GET (the chain's own landing comes);
- a GET older than one cadence that never answered → one new GET; when the old one answers (or rejects) later,
  `loadAll` drops it (`my !== loadSeq.current`) — it changes nothing and arms nothing.

## Nothing happens when

- the tab is still hidden (a `visibilitychange` that does not make it visible);
- the last full GET is younger than one served `refresh_sec` (the armed timer still fires on time);
- out of window (`refresh_sec` 0), `owner_only`, no board yet;
- after unmount (listener removed; `alive` guard).

The live-interest POST (`hooks/useGgwLive`) keeps its own return rule; this effect adds no POST.

## Tests

- `frontend/src/lib/ggwReturn.test.ts` — the rule (true / exact cadence / NEGATIVES hidden, 0, negative, NaN,
  younger) and the parameter keys pinned (no in-flight input).
- `frontend/src/components/GajjalaWatchBoard.return_refetch_2026_11_23.test.tsx` — the real board: hidden across a
  tick → 0 GETs; return → exactly one; next one `refresh_sec` after that landing (59.9 s none, +0.2 s one); five
  rapid hide / show → still one; [C9] a dead GET ≥ one cadence old → one new GET, its late answer / rejection
  changes nothing and arms nothing; NEGATIVES young GET (done or in flight), still hidden, out of window,
  owner_only, unmounted, live POST count; source guards (`ggwReturnRefetch(` once, one listener, the issue stamp, no
  `30_000` / `60_000`, no `fullBusy`, `ggwRowLive(r)` kept).

## Effect

UNMEASURED. Bound: on return the bars were up to one extra cadence old; now one GET at once when the last one is at
least one cadence old.

## HIS CALL

- A GET on EVERY return (even 2 s away) needs a minimum-gap number — not built (spec §7 #6).
- The same return rule on the 🚩 / 🧪 / 🥇 boards — not built.
