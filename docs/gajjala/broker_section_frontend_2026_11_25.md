# 🚫 🧠 Potential bottom section — frontend (2026-11-25)

Spec: fidsec rev 2 §3.2–§3.3 (work package fe-section). Backend half: `broker_section_2026_11_25.md`.

## The ask, verbatim

Ajay 2026-11-25 ~10:25 ET:

> On the potential page move the no fidelity to the bottom segmented category.,
>
> Show me only EMBC

Built IN PART: **a header was added above the 🚫 cards; nothing moved.** Those cards have sat last since 2026-11-09
(`tab.broker_bottom`). 📈 Track rows and the 👀 line are untouched (they still carry 🚫 names interleaved). What he
wants moved, and "Show me only EMBC", are HIS CALL (spec §7 items 1–2) — nothing was built for line 2.
Display only. No gate, rule, threshold, push, count or order changes. UNMEASURED.

## The header

- Words: ONLY the served `broker_flags.section.text` (`"{BROKER_FLAG_TEXT} · {n}"`, e.g. `🚫 not eligible at <broker> · 1`)
  plus the structural ▾ / ▸ on the phone. No hint, no explanation line. The FE types no word about a stock.
- Parsed by `lib/ggBrokerSection.parseGgBrokerSection` through the 👀 Watch `parseSections` (ONE engine); junk, no words or
  no symbols → nothing drawn.
- Tail guard (`ggBrokerSectionStart`): the header prints before the first DRAWN card of the section, and only when every
  drawn card after it is in the section — an unlisted card is never labelled.
- ONE gate: the backend constant `BROKER_SECTION_SUBS`. The FE holds no sub list — any served block that parses and passes
  the tail guard draws (a test pins a served block on `bull_flag` drawing). Kill switch: `BROKER_SECTION_SUBS = ()`.
- Owner only by construction: the block lives inside the owner's `broker_flags`; a non-owner gets `broker_flags: null`.
- 0 🚫 cards → the key is absent → the DOM is byte-identical to before (pinned by `innerHTML` equality).
- The header is ONE keyed `<h3>` spliced in as a SIBLING of the cards (`ggSectionSplice`), never a wrapper — no card remounts
  (no chart redraw) when the section appears or disappears (pinned by node identity across the 🚫 toggle re-read, both ways).
  The pinned literal `liveTiles.map((t) => {` (contracts.mjs live-card block) survives verbatim inside the splice.
- The 🔝 Focus divider and the header are independent siblings: today's live board shows divider then header back to back
  (§7 item 8). An impossible payload (a card both 🔝 and 🚫) still draws both, no card lost.

## The three layouts

1. **Default grid, desktop** — a plain header, always open, no control. **The desktop in-grid header is new, not the Watch
   pattern** (the 👀 Watch draws no in-grid header on desktop) — HIS CALL (§7 item 4).
2. **Default grid, phone** (`GGW_PHONE_MQ`, ≤ 640 px) — the Watch's own fold button (`.ggw-section-btn`, ▾ / ▸,
   `aria-expanded`). A tap hides the 🚫 cards with the `hidden` attribute; they stay in the DOM, in served order, and still
   feed the room POST, the live poll and the ⤢ stepper. Starts folded ONLY when the server serves `folded_default: true`
   (backend `BROKER_SECTION_FOLDED_DEFAULT`, shipped False).
3. **Opt-in 👀 Watch layout (paged)** — the existing pager `groups` label (`ggc-pager-group-broker`) before the first 🚫
   ticker; no in-grid header, no fold. **Watch layout + one card = no label, the chip still prints** (the pager renders only
   for more than one card). Accepted and pinned.

## Phone fold storage (per browser, try/catch)

- `gg.section.collapsed` — JSON list of served keys he folded (the `ggw.collapsed` format).
- `gg.section.opened` — JSON list of default-folded served keys he opened (the `ggw.opened` format).
- Written ONLY by his tap or the focus reveal — never on mount. Junk / blocked storage → empty lists (open). Folding uses
  the Watch helpers `ggwFoldedKeys` / `ggwToggleFold`; desktop is never folded.

## Focus deep link

`?focus=<🚫 sym>` into a folded section opens it first (once per focus value, StrictMode-safe via a ref), and the existing
once-per-focus scroll waits for that (`if (focusFolded) return;`), then scrolls the now-visible card. `?focus=<other>`
leaves the section folded.

## 430 px rule

`.ggw-section.gg-broker-section` (appended at the end of `gajjala.css`, specificity 0,2,0 over `.ggw-section`):
`grid-column: 1 / -1; min-width: 0; max-width: 100%; overflow-wrap: anywhere;` — a whole grid row that wraps.
`.cm-grid > .gg-card[hidden] { display: none; }` keeps a folded card hidden whatever sets `display`.

## Files

`frontend/src/lib/ggBrokerSection.ts` (+ `.test.ts`), `lib/gajjala.ts` (`GgBrokerFlags.section?: unknown`),
`components/GajjalaBoard.tsx`, `components/GgCardGrid.tsx` (optional `groups` → `GgwPager` only),
`components/GajjalaWatchLayout.tsx` (one comment line), `styles/gajjala.css`,
`components/GajjalaBoard.broker_section.test.tsx`.
