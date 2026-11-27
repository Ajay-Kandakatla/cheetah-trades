# 🏁 SI follow fold + 🩳 6-K issuance link — frontend (2026-11-26)

Spec: sishares §3.6 / §4.4 (WP fe). Ajay 2026-11-26: "Fix the POM chip and the 6-K dilution check." ·
"lets track them in our list of SI. and maintain a track record of our stocks".

## 2026-11-26 — what the frontend draws

**Follow fold** (`frontend/src/components/GgSiTrack.tsx`). The 🏁 SI track record body gains ONE nested, closed
`<details data-testid="gg-st-follow">` after the day tables and before the 🏁 rule fold. Its summary is the served
`follow.summary_text`. The body mounts only while the fold is open. In order it shows: the title, the caveat (no
comparison group, UNMEASURED), the as-of, the base lines, the empty line, the names table, the served pinned label with the
pinned table (or the served `pinned_empty_text` when there are no pins), the shown and pending lines, and a nested rule fold.
Every word and number is served by `backend/chart_maps/gajjala/si_follow.py`. The component formats no number, sorts
nothing and fetches nothing.

Guards:
- `follow` that is absent, null, an array, a number or has no summary → no fold, and the 🏁 body DOM is unchanged.
- A row with no served symbol is dropped.
- A NaN, number or empty cell prints nothing.
- An href that fails `ggHref` (not an in-app `/` path) prints as plain text.
- A served `fault_text` still prints alone.

The day table needs no change: its +5 sessions column arrives as a served head (`f5`) and cell. Types:
`GgSiFollowBlock`, `GgSiFollowName` and `GgSiTrackBlock.follow` in `frontend/src/lib/gajjala.ts`. CSS:
`.gg-st-follow` in `frontend/src/styles/ggSiTrack.css` uses the 🏁 wrap rule (min-width 0, max-width 100%, overflow-wrap
anywhere), and each table scrolls inside its own `.gg-tr-scroll` box at 430 px. Nothing new shows outside the ⓘ fold.

**6-K issuance link** (`frontend/src/lib/shortInterest.ts`, `frontend/src/components/ShortInterestPanel.tsx`).
`SI_FILING_URL_PREFIX = 'https://www.sec.gov/Archives/edgar/data/'`. `siIssuances(read)` reads the served
`basis.issuances` and returns `{label, text, url | null}[]`:
- An entry without a non-empty served label is dropped.
- A url is kept only when it starts with the prefix and holds no whitespace, quote, angle bracket or backslash. So
  `http://`, another host, a look-alike host (`www.sec.gov.evil.com`), `javascript:` and `data:` all give no link.
- No basis, an older API or a non-array gives `[]`.

On the ticker page's Smart Money tab, the 🩳 panel lists each issuance that has a link under the rows. The link uses the
served label, `target="_blank"` and `rel="noopener noreferrer"`, and its hover is the served text. With no linked issuance
the panel is byte-identical to before. The issuance words are also served inside the rows ("Share issuance").

Tests:
- `frontend/src/components/GgSiTrack.test.tsx`: the follow describe block, with negatives.
- `frontend/src/components/GgSiTrack.payload.test.tsx`: reads the golden whether or not it carries `follow`.
- `frontend/src/lib/shortInterest.basis.test.ts`: `siIssuances`.
- `frontend/src/components/ShortInterestPanel.test.tsx`: the link attributes, and that the panel is unchanged without
  issuances.

Display only. No gate, sort, push or lane input. UNMEASURED.
