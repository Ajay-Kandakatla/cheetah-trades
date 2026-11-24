# 🧹 The ⓘ fold store on 🚩 Gajjala's landing — 2026-11-24 (ggclean, WP fold-core)

Ajay 2026-11-24, three messages with screenshots:

1. "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages anymor"
2. "Add all of this too"
3. "Collapse all of this too"

This page covers the engine only: `frontend/src/lib/ggFold.ts`, `frontend/src/components/GgFold.tsx` and
`frontend/src/styles/ggFold.css`. Where the folds sit on the page is in `landing_declutter_2026_11_24.md` (board),
`landing_declutter_page_2026_11_24.md` (Chart Maps rows) and `landing_declutter_panels_2026_11_24.md` (panels).

## Store keys and the default

| localStorage key | what it remembers |
|---|---|
| `gg-fold:header` | the ONE header fold on 🚩 (`GG_FOLD_HEADER`) |
| `gg-fold:sub:<sub>` | each sub's own fold (`ggFoldSubKey(sub)`, e.g. `gg-fold:sub:high_si`) |

- `'1'` = open, `'0'` = closed. Absent, junk (`'true'`, `'open'`, `''`, anything else) or blocked storage = CLOSED
  (`GG_FOLD_DEFAULT_OPEN = false`, his "hidden by default").
- Read once per key per page into a module cache. `useGgFold(key)` uses `useSyncExternalStore` + module listeners
  (the `ggWatchList.ts` pattern), so every hook on one key moves together in the same document (page rows + board rows
  + panel text). Another key never moves.
- A blocked `setItem` (private mode, quota) still toggles for the visit: the cache holds it, nothing throws.
- No `storage` event listener: cross-tab sync was not asked.
- `useGgFold(null)` = no fold here: `on` false, `open` true, toggle writes nothing.
- The ⓘ counts opens with `trackFeature('gg-fold:<key>')` (opens only, not closes) so lines he never opens can later be
  judged on a number.

## The `[hidden]` twin trap

The body is hidden with the HTML `hidden` attribute and stays MOUNTED (no served text deleted). This app has no global
`[hidden] { display: none }` rule, and `.gg-fold-body { display: flex }` would beat the browser's own `[hidden]` rule,
so the sheet carries the twin right under it:

```css
.gg-fold-body { display: flex; flex-direction: column; gap: 0.45rem; min-width: 0; max-width: 100%; }
.gg-fold-body[hidden] { display: none; }
```

It wins by specificity (0,2,0 over 0,1,0), never by sheet order. vitest runs with `css: false`, so tests read the
`hidden` attribute (`toBeVisible`) and guard the twin by reading the stylesheet source (`GgFold.test.tsx`).
Same trap, same fix as `gajjala.css:430` and `gajjalaWatch.css:214`.

The ⓘ sits at its row's right end (`margin-left: auto` on `.gg-actions > .gg-fold-toggle`, `.cm-phase > …`,
`.gg-all-head > …`) so it does not jump when the 🧾 button arrives after its own GET.

## The answer to the scan on open

The owner's page POSTs a scan once when it opens. Its answer folds with the header only when its served state key is
one of `GG_FOLD_SCAN_ON_OPEN` = `started`, `waiting`, `reused`, `closed` (`ggFoldScanAnswer(state)`: exact,
case-sensitive string match on the served key, never on words). On a closed market that answer would otherwise be a
third line for the whole visit.

`refused` (including the store error) and any unknown state stay OUT of the fold: a refusal is a fault, and a fault stays
visible. An answer to HIS tap on 🔄 is never folded, whatever its state (the board decides origin; this module only
answers "is this state foldable").

## Adding a fold elsewhere

1. Pick a key: a new constant in `ggFold.ts` (never a typed word), or `ggFoldSubKey(sub)` for a sub.
2. Put `<GgFoldToggle k={key} testid="…" controls="<body id>" />` where the ⓘ goes (a null key renders nothing).
3. Wrap the text in `<GgFoldBody k={key} id="<body id>" testid="…">…</GgFoldBody>`. Several bodies may share a key;
   one carries the `id`. A null key renders a bare fragment (the DOM-identical path for every other variant).
4. Under a `GgSubFoldContext.Provider value={key}` both components take the key from context when `k` is absent.
   Both hooks are called unconditionally (`useContext` first, then `useGgFold`) — never `useContext` in a ternary.
5. If a fault or an empty / chartless line would hide with the body, print it while closed with
   `<GgSubState lines={…} />` (served lines only; it prints nothing while the fold is open).
6. Tests: closed by default, `not.toBeVisible()`, a null-key negative, and the panel's lines verbatim.
