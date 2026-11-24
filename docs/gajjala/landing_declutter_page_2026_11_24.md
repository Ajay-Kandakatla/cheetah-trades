# 🧹 🚩 Landing declutter: the Chart Maps page rows (2026-11-24)

Ajay, 2026-11-24, in three messages with screenshots:

> "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages anymor"
> "Add all of this too"
> "Collapse all of this too"

Spec: `ggclean` §3.4, work package `page`. This change is FRONTEND ONLY. No served word changed.

## What moved

`frontend/src/pages/ChartMaps.tsx` draws three rows above every tab body:

| row | built as |
|---|---|
| WHY blurb (`StudyNote id={`blurb-${tab}`}`, already folded to its first sentence since 2026-09-20) | `blurbEl` |
| ℹ️ Rules × 2: 🧨 `explosive` and 🩳 `short_interest` | `houseRulesEl` |
| 🎯 Enterable only + its ℹ️ Rules (`enterable`) | `enterableBarEl` |

The JSX of the three blocks moved without changes into consts that are built before `return`. `const ggHeadTab = tab === 'gajjala'`.

- **🚩 `gajjala`**: the three original positions render nothing. The tab body is wrapped in
  `<GgHeadPageContext.Provider value={<>{blurbEl}{houseRulesEl}{enterableBarEl}</>}>`. `GajjalaBoard` reads the
  context and prints `{headPage}` first inside segment A of its closed ⓘ header fold (`gg-head-body`).
- **Every other tab**, including 🧪 `gajjala_audited` and the retired `gajjala_1m`: the context value is `null` and the
  three rows render where and as they always did, outside any fold. A stored open `gg-fold:header` key has no effect on
  those tabs.

## Why a context and not hiding the rows in place

- **Not hidden in place, above the toggle.** The fold would then open ABOVE the ⓘ he just tapped. iOS Safari's scroll
  anchoring cannot be relied on, so the toggle would jump down about three rows. Passed through the context, the rows
  open DOWNWARD under the 🔄 · 🧾 · ⓘ action row, in the order blurb → ℹ️ × 2 → 🎯 row → board strip.
- **Not a portal.** A portal brings slot timing and remount risk. A context carrying the same JSX has one
  implementation, and each row exists only once in the DOM.
- **Not native `<details>`.** The fold body spans two components, the page and the board, and the two buttons cannot
  live inside a `<summary>`.

## What did not change

- **🎯 Enterable only** writes and drops `?show=all` exactly as before. `enterableOnly` / `setEnterableOnly` are
  untouched, and the checkbox is inside the fold. It still hides no 🚩 card, because `GajjalaBoard` never reads
  `useEnterableFilter`. Whether to put a "🎯 on" marker beside ⓘ is his call (spec §7 #3).
- These are byte-identical: the `<GajjalaBoard />` mount line, `splitBlurb(TAB_META[tab].blurb)`, the `<StudyNote id={`blurb-${tab}`} … headline={head}>`
  literal, `<EnterableOnlyToggle `, `<RulesInfo section="enterable"`, `"explosive"` and `"short_interest"`. All
  219 contracts are green.
- **A stubbed board** is a page test that mocks `GajjalaBoard`, so nothing consumes the context. Such a test renders
  without a crash, and on 🚩 the three rows are simply absent (spec §6 #8). A new test of these rows must use the real board.

## Tests

`frontend/src/pages/ChartMaps.ggHead.test.tsx` covers the real page and the real `GajjalaBoard`, with fetch stubbed,
a Map-backed `localStorage` and `resetGgFold()` run in each test. It has 15 cases:

- On 🚩 by default, the blurb, the three pills and the 🎯 checkbox are inside `gg-head-body` and are not visible. Each
  row appears once, inside `.gg-board`.
- The only visible text between `cm-tabs-bar` and `.gg-subs` is the served scan label, `🧾 log trade` and `ⓘ`. In this
  case the stubbed scan-on-open POST answers `closed`, and that answer (`gg-scan-reused`) is in the DOM but folded [C1].
- One tap on ⓘ makes all three rows visible, in order, under `gg-actions`, and writes `gg-fold:header` = `'1'`.
- With the fold open, 🎯 unticked → `?show=all`; ticked → the param is dropped. The 🚩 tile ids are the same both ways.
- NEGATIVE cases:
  - On `zones`, `bonde`, `gajjala_audited` and `gajjala_1m`, the rows are in place and visible, sit in no
    `.gg-fold-body`, and there is no ⓘ toggle. This holds both with and without a stored open header key.
  - When `getItem` throws, the page renders with the fold closed.
  - With a stubbed board, there is no crash and the rows are absent on 🚩, while `zones` still shows them.

Two mutation checks were run and then reverted. With `ggHeadTab` also true for `gajjala_audited`, 2 cases go red. With
`ggHeadTab = false`, 5 cases go red.
