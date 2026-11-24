# 🩳 High SI sub — frontend (2026-11-23, WP fe-sub)

Ajay 2026-11-23 (voice-typed): "Can you create a tab similarly like Divergent with high charging tested, SHO tag, and low
floats similar to what we've done in Divergent tab under Gazilla?" — then "New tab like divergence*".
[voice typing: "high charging tested" = high short interest, "Gazilla" = Gajjala]

Spec: high SI spec §3.8 / §4 WP `fe-sub` (ship shapes S1 and S2). Backend: `docs/gajjala/high_si_sub_2026_11_23.md`.
Information only, never an entry. UNMEASURED. Not advice.

## What the frontend changed

| File | Change |
|---|---|
| `frontend/src/lib/gajjala.ts` | `GgSub` gains `'high_si'`; `GG_SUBS` gains `{ key: 'high_si', emoji: '🩳', label: 'High SI' }` right after 🌱 Diverging (== backend `constants.SUBS`, 14 subs); `GG_HIGH_SI_SUB`; type `GgHighSiBlock`; `GgBoard.high_si` |
| `frontend/src/components/GgHighSi.tsx` (new) | `GgHighSiPanel({ block })` — the served panel above the cards |
| `frontend/src/components/GajjalaBoard.tsx` | two lines (see below) |
| `frontend/src/lib/navSearch.ts` | `GG_SUB_WORDS.high_si` — high si, short interest, shorts, low float, reg sho, threshold, hard to borrow, ema cross |

### The board — two lines, nothing else

1. ONE more GG5-only filter on the pre-board fallback strip, chained after the 🌱 one:
   `.filter((s) => vkey === 'gajjala' || s.key !== GG_HIGH_SI_SUB)`. The two contract-pinned clauses (📋 / 🧨) and the 🌱
   filter are byte-identical. The 1-minute, 🧪 Audited and 🥇 Luk pages never flash the 🩳 chip.
2. `{activeSub === GG_HIGH_SI_SUB ? <GgHighSiPanel block={board.high_si ?? null} /> : null}` right after the 🌱 panel line.

The bar-size toggle STAYS on the 🩳 sub (5m / 15m — the cross reads both frames; the toggle line that hides it on 🧨 / 🌱
is untouched). The cards, the 🩳 / 🔒 / 💸 / 🚫 chips, ➕ Watch and the 📺 view are the existing ones. A criteria row served
with `ok: null` (the "judged at the ring" volume row, a frame with no cross) draws the `·` mark and class `gg-unjudged` —
neither ✓ nor ✗ (the existing renderer; pinned, no code change).

## The panel — lines and testids, in order

Every string is served and printed as handed, through the `servedText` guard (a NaN / undefined / number / empty string
prints nothing). The component types no word and no number (the `ⓘ` fallback summary aside). With the push off the served
`push_text` is the 🔕 sentence — the panel prints whatever is served and knows nothing of the mode.

| # | testid | served key | where |
|---|---|---|---|
| — | `gg-hs` | (root, class `gg-dv`) | |
| 1 | `gg-hs-title` | `title` | always visible |
| 2 | `gg-hs-ask` | `ask_text` | always visible |
| 3 | `gg-hs-counts` | `counts_text` | always visible |
| 4 | `gg-hs-adds` | `adds_text` | always visible |
| 5 | `gg-hs-asof` | `asof_text` | always visible |
| 6 | `gg-hs-sho` | `sho_text` | always visible |
| 7 | `gg-hs-push` | `push_text` | always visible |
| 8 | `gg-hs-order` | `order_note` | always visible |
| 9 | `gg-hs-shown` | `shown_text` | always visible |
| 10 | `gg-hs-empty` | `empty_text` — only when `n === 0` and no chartless line | always visible |
| 11 | `gg-hs-chartless-{SYM}` | `chartless[].text`, else `chartless[].state_label` (a Link through `ggHref`) — refix 2026-11-23 | always visible |
| 12 | `gg-hs-faults` | `faults_text` | always visible |
| 13 | `gg-hs-rule` | `<details>`, summary = `rule_label` (else `ⓘ`) | folded |
| 13a | `gg-hs-rule-text` | `rule_text` | inside the fold |
| 13b | `gg-hs-cohort` | `cohort_text` | inside the fold |
| 13c | `gg-hs-excluded` | `excluded_text` | inside the fold |
| 13d | `gg-hs-disagree` | `disagree_text` | inside the fold |
| 13e | `gg-hs-notier` | `no_tier_text` | inside the fold |
| 14 | `gg-hs-honesty` | `honesty` | LAST, always visible |

The fold draws when any of 13a–13e is served (a name list with no rule text still folds under `ⓘ`). A null / absent block
(an older API, or the short-interest read faulted — the board's served `empty_note` says so) draws no panel.

## Phone (430 px)

The three name lists and the cohort sentence sit inside the `<details>`, so the header stays short above the cards. The
root is the existing `gg-dv` class (`min-width: 0; overflow-wrap: anywhere`, `gajjala.css`); no inline width, no `nowrap`
(both pinned by tests).

## Tests

- `frontend/src/components/GgHighSi.test.tsx` (new, 25) — served order, honesty last, `gg-hs-adds` visible, fold contents,
  push sentence as served; NEGATIVES: null / undefined / non-object block, NaN / number / '' / undefined on every line
  (adds, disagree, no tier included), empty line only on `n === 0` with no chartless line, unsafe hrefs, no digit in code,
  no b-word, no inline width / nowrap.
- `frontend/src/components/GajjalaBoard.high_si.test.tsx` (new, 19) — the served strip "🩳 High SI · n" after 🌱; the panel
  above the cards; criteria rows (ok null → `gg-unjudged`, no ✓ / ✗); the 🩳 / 🔒 / 💸 chips, the 🚫 chip when served, ➕
  Watch on a chartless card; the toggle drawn on 🩳; NEGATIVES: fallback strip of 1-min / 🧪 / 🥇 omits 🩳, no panel on
  🌱 / 🧨 / 🚩, toggle still hidden on 🌱 / 🧨, `high_si: null` → served `empty_note` only, older API → no panel, NaN fields,
  source guards (the pinned clauses byte-identical, ONE chained filter).
- `frontend/src/lib/gajjala.test.ts` — 14 subs, `high_si` after `diverging`, `GG_HIGH_SI_SUB`, `parseGgSub('high_si')` /
  `' High_SI '`; NEGATIVE `'high-si'`, `'highsi'`, `'high_si_'`, `'short_interest'` → the default sub.
- `frontend/src/lib/navSearch.test.ts` — "short interest", "high si", "reg sho", "hard to borrow" find the 🩳 row.
- Widened (strip pins, `WIDENED 2026-11-23 — 🩳 High SI after 🌱`): `GajjalaBoard.divergence.test.tsx`,
  `GajjalaBoard.diverging.test.tsx`.

**Refix 2026-11-23 — a chartless line names its ticker.** The served chartless `state_label` is the tier only
("🩳 High short interest"), so a line printed from it alone hid which name it was. The panel now prints the served
`text` (`high_si.CHARTLESS_TEXT`, "🩳 SYM listed · chart not stored") and falls back to `state_label` only when `text` is
not a served string; a line prints when either is served, so a name whose read raised (`state_label` null) is never
dropped. Type: `GgHighSiChartless = GgDivergenceChartless & { text?: string | null }` (the 🌱 type is unchanged). No
backend wording moved; no golden moved. Tests: `GgHighSi.test.tsx` "2026-11-23 refix: the chartless line prints the
served text …" (NEGATIVES: NaN / blank text → state_label; neither served → no line) and
`test_gajjala_high_si_2026_11_23.py::test_chartless_no_bars_line_names_the_ticker_in_the_served_text`.
