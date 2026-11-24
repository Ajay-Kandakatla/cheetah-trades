# ⛔ New SSR names — the 🩳 High SI panel section (frontend, 2026-11-24)

Ajay 2026-11-24: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones".
Spec: `ssrlist` §3.4, work package W3. Display only. UNMEASURED.

**2026-11-24.** `GgSsrNewSection` (`frontend/src/components/GgSsrNew.tsx`) prints the served `high_si.ssr_new` block inside the
🩳 panel (`GgHighSi.tsx`), after the faults line and before the ⓘ fold — one digit-free line in the panel, so the panel's
three-digit pin, its `gg-hs*` testid order and its last child (`gg-hs-honesty`) do not move. Every string is served by
`high_si.ssr_new_block` over `ssr.new_triggers`; the component types no word, formats no number, never sorts, counts or
fetches, and never prints `n` / `n_untiered`.

- Always visible, each only when a served non-empty string, in this order: title (`<h4>`), counts, tier note [C2], window,
  as-of, status, partial (cm-note), SI note, list note, faults, fault (cm-note cm-note-err), empty.
- A served `fault_text` means no fold and no empty line, whatever else is served.
- One `<details>` per served fold (served summary + at least one row with a served symbol), in the served order. Its rows
  are MOUNTED ONLY WHILE THE FOLD IS OPEN (state from `onToggle`; served `open: true` opens it at first paint) — the
  "every other name" fold is ~600 rows today and costs no DOM while closed.
- A row: the ticker (a `<Link>` only through `ggHref` — a `//…`, `http://…`, `javascript:` or non-string href is plain
  text), then the served at / drop / source / mark / 🩳 texts, each in its own span; the dot separator is CSS.
- Last: the ⓘ rule fold, drawn only under a served `rule_label`, holding the rule, the note, the order note and the
  withheld line.
- Types `GgSsrNewRow` / `GgSsrNewGroup` / `GgSsrNewBlock` and `GgHighSiBlock.ssr_new` in `lib/gajjala.ts` (the sub's
  literal is still typed exactly three times there).
- Styles: `.gg-ssrn*` rules appended to `styles/ggSsr.css` after its `@media` block — `min-width: 0`,
  `overflow-wrap: anywhere`, rows in `repeat(auto-fill, minmax(17rem, 1fr))`; neutral colours, semibold at most, no fixed
  width; the sheet's single no-wrap word is still the fitted 👀 tile rule. `gajjala.css` holds no `gg-ssrn`.

Tests: `frontend/src/components/GgSsrNew.test.tsx` (18, negatives on every piece: junk block, junk texts, the fault line,
closed folds, served order, junk folds / rows, unsafe hrefs, no typed word, the panel placement, the sheet pins, the source
guards). Mutation: dropping the FE fault guard turns test 4 red.

Not done here: the ✨ entry, the `contracts.mjs` lines and the phone check on real data (main session, spec §4 / §5.5).
