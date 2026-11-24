# 🧹 🚩 Landing declutter — the panels (2026-11-24, ggclean spec §3.6, WP `panels`)

Ajay 2026-11-24:

- "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages anymor"
- "Add all of this too"
- "Collapse all of this too" (the 🩳 High SI panel text down to the tally line and its ⓘ)

FRONTEND ONLY. No served word is added, deleted or reworded. The panels keep their signature, markup and order; the
board (`GajjalaBoard.tsx`, WP `board`) wraps them in the sub's own closed ⓘ fold (`GgFoldBody`, key `sub:<sub>`,
stored as `gg-fold:sub:<sub>`, default CLOSED). The text stays MOUNTED, hidden with the `hidden` attribute.

## What folds on which sub

| sub | folds (inside the sub's closed ⓘ) | stays visible |
|---|---|---|
| 🩳 high_si | `GgHighSiPanel` whole: title, ask, counts, adds, as-of, 🔒, 🔔 push, order, shown, ⛔ SSR section (`GgSsrNew`), ⓘ rule fold, honesty — then the tally + ⓘ | the cards; the state lines below |
| 🧨 divergence | `GgDivergencePanel` whole: title, ask, two in-sample lines, OOS, cohort, window, order, ⓘ rule, honesty — then the tally | the cards; the 🏁 fold below them; the state lines below |
| 🌱 diverging | `GgDivergingPanel` whole: title, ask, two picks, cohort, window, bars, order, ⓘ rule, honesty — then the tally | the cards; the state lines below |
| 📋 all_strategies | the served order text (`gg-all-order`, or the near-sort `near_text`) — inside `gg-sub-body-table` | the title (with the ⓘ beside it in `gg-all-head`), the sort chips, the table, the more / fault / si-fault / empty / honesty lines |

## The state lines that stay OUTSIDE the fold — `GgHighSiState`, `GgDivergenceState`, `GgDivergingState`

Each panel file gains ONE additive export that the board renders under the controls row. It returns
`<GgSubState lines={…} />` (`GgFold.tsx`), which prints only WHILE THE SUB'S FOLD IS CLOSED — open, the panel prints the
same lines in place, so a line is never twice on screen. In the panel's own order, under the panel's own rules:

| kind | served field | when | why it stays visible |
|---|---|---|---|
| `empty` | `empty_text` | 🩳 / 🌱 `n === 0`, 🧨 `n_today === 0`, and no chartless line | no card is drawn — the grid alone would look broken |
| `chartless` | 🩳 `text` (else `state_label`); 🧨 / 🌱 `state_label`; `href` as served (through `ggHref`, an unsafe one prints as text) | one per served listing that drew no card | a name is missing from the cards |
| `faults` | `faults_text` | when served | names could not be read this time |
| `fault` key `ssr` (🩳 only) | `ssr_new.fault_text` | when served | the ⛔ SSR list could not be read (§7 #1) |

Not outside (inside the fold, his call §7 #1): `ssr_new.partial_text` / `faults_text`, the " · not every Reg SHO list was
read" tail of the 🩳 order line, the short-interest as-of line.

**One selector.** The chartless filter and the show-empty test live in ONE private function per file (`listed`), used by
both the panel and the State export, so the two can never disagree. `block.n === 0` stays single in `GgHighSi.tsx`
(the 3-digit guard, `GgHighSi.test.tsx`). The `gg-hs-faults` line, the `<GgSsrNewSection block={block.ssr_new} />`
mount line and the `{folded ? (` line did not move (`GgSsrNew.test.tsx` pin). `GgSsrNew.tsx` gained a comment only.

## 📋 `GgAllTable` — context-driven

`useGgSubFold()` (called before the early return) reads `GgSubFoldContext`. With a key: the title row becomes
`<div class="gg-all-head">` + `GgFoldToggle testid="gg-sub-toggle" controls="gg-sub-body-table"`; the order text sits in
`GgFoldBody id="gg-sub-body-table"`. With no provider or a null key (🧪 Audited, the retired 1-min page, every standalone
use) `GgFoldBody` is a bare fragment and no toggle renders — the DOM is today's (pinned: same `innerHTML`).

## Tests

`GgHighSi.test.tsx`, `GgDivergence.test.tsx`, `GgDiverging.test.tsx` (the State block each), `GgAllTable.test.tsx`
("🧹 📋 sub fold"). Equality pins: the strings and hrefs the State prints equal the panel's for the same block. Negatives:
fold open (set or stored `'1'`) → nothing; another sub's open flag → no effect; no context → nothing; nothing served →
no root; null / junk block → nothing; NaN / number / "" → nothing; `n > 0` or a chartless line → no empty line; an
unsafe href → text; 📋 with no context → no toggle, no wrapper, the order line visible. Mutations checked red: unwrap the
📋 body, drop the SSR line, drop the chartless guard from the empty test (🌱), invert the 🧨 empty test.
