# ⛔ SSR tag — the frontend half (2026-11-23, spec ssr §3.10, package W4)

Ajay, 2026-11-23:

> "No shorting at the bid (SEC short-sale restriction)
>
> Can we check or this for other stocks too?"

Display only. The frontend draws what `GET /short-interest/ssr?symbols=A,B,C` serves and nothing else: no push, gate,
sort, filter or lane reads it. UNMEASURED. The rule, the exchange lists, the computed read and every word live on the
backend (`backend/short_interest/ssr.py`, `docs/short_interest/ssr_rule_201_2026_11_24.md`).

## Files

| File | What it does |
|---|---|
| `frontend/src/lib/ssr.ts` | `SSR_PATH`, `SSR_KIND = 'ssr_rule_201'`, `parseSsr`, `ssrRead`. Rejects any body whose `kind` is not `ssr_rule_201` (the 🔒, 💸 and 🩳 bodies included). Keeps an item only with a non-empty `state`, a non-empty `title` and at least one non-empty form (chip / short / label). Skips a `__proto__` key. Exact own-key lookup (trimmed, upper-cased ask). |
| `frontend/src/hooks/useSsr.ts` | `useBorrow.ts` re-keyed. Microtask batch → ONE GET per commit, chunks of `SSR_CHUNK = 200` (== the served `max_symbols`, backend `read.MAP_MAX_SYMBOLS`). Life of an entry = min(`SSR_TTL_MS` 300 000, the served `keep_sec`, the clamped `retry_after_sec`). A failed refetch keeps the held read inside the served `keep_sec`, else nothing; retries after `SSR_RETRY_MS`. The only timer: `refreshing` → at most `SSR_FOLLOWUP_MAX` re-asks, delay clamped to `SSR_FOLLOWUP_MIN_MS`…`SSR_FOLLOWUP_MAX_MS`. `useSsrFault()` = the newest valid payload's `fault_text`; a later valid payload without one clears it; a failed request leaves it. `_resetSsrCache()` for tests. |
| `frontend/src/components/GgSsr.tsx` | `GgSsrChip` (served `chip`, or `short` with `form="short"`), `GgSsrLabel` (served `label`), `GgSsrFault` (served `fault_text`). Hover = the served `title`; `data-ssr-state` = the served state. A null form, no item or no valid payload → NOTHING (no wrapper; `lead`'s single space only when drawn). |
| `frontend/src/styles/ggSsr.css` | `.gg-ssr` wraps on the 430 px phone (`white-space: normal; overflow-wrap: anywhere; min-width: 0; max-width: 100%`); `.gg-ssr-label` weight 600; the fitted 👀 Watch tile above 640 px ellipsises on one line. Neutral look: no alarm or tier colour. |

## What is drawn, per served state

| Served | 🚩 / 🧪 card head | 🎾 Reversal Squeeze card | 👀 Watch tile head |
|---|---|---|---|
| `on` (official or computed; a computed one carries the served ` · computed`) | the served `chip` | the served `label` | the served `short` |
| `unknown` with a served label (e.g. `corp_action`, `no_prior_close`) | nothing (chip served null) | the served `label` (`⛔ SSR not read`) | nothing (short served null) |
| `off`, or a quiet unknown (`computed_only`, `awaiting_first_scan`) | nothing — the server sends no item | nothing | nothing |
| a failed GET / a foreign body | nothing | nothing | nothing |

The served `fault_text` prints once above the card grid (`gg-ssr-fault`), never on a tile.

## Placement (one added line each, order 🩳 → 🔒 → 💸 → ⛔)

- `GajjalaBoard.tsx`: the import after the 💸 import; `<GgSsrFault testid="gg-ssr-fault" />` right after the 🔒 grid
  fault line; the chip right after the 💸 chip on a non-🎾 card (`gg-ssr-<SYM>`); the label right after the 💸 label on a
  🎾 card (`gg-ssr-label-<SYM>`).
- `GajjalaWatchTile.tsx`: the import after the 🔒 import; the short chip right after the 🔒 short chip, behind the same
  `siNote` prop (`ggw-ssr-<SYM>`, also in the ⤢ view).
- NOT placed: the 📋 All strategies table (HIS CALL 6). No Watch-board fault line (not in the spec).

## Tests

`lib/ssr.test.ts`, `hooks/useSsr.test.ts`, `components/GgSsr.test.tsx` (incl. the source guards: no typed SSR word, no
compare on a served field, no email, phone wrap, `nowrap` only in the fitted-tile media rule),
`components/GgSsr.payload.test.tsx` (the backend golden `backend/tests/fixtures/ssr_payload_2026_11_24.json`, or
`SSR_LIVE_PAYLOAD=<abs path>`, through the real components; a missing file FAILS),
`components/GajjalaBoard.ssr.test.tsx`, `components/GajjalaWatchTile.ssr.test.tsx`.
One existing pin widened: `GajjalaWatchBoard.fixes.test.tsx` — its fetch stub answers the new `/short-interest/ssr` GET
outside the Watch-read counter (`// WIDENED 2026-11-23 (⛔ SSR GET)`).
