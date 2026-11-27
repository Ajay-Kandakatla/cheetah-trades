# 🧘 GG-like calm check — frontend core (2026-11-27)

Ajay 2026-11-27: "find calmer and better setups.. I want to make sure we are finding similar setups to Gajjala".
Spec: `scratchpad/gglike/spec.md` §3.9, work package `fe-core`. Scope 🟡: a display of how a read compares to GG's own
example charts. Nothing rings, gates, sorts or reorders. UNMEASURED.

**2026-11-27 — the shared lib and components.** `frontend/src/lib/ggLike.ts` parses the served blocks strictly: a
verdict outside `gg_like` / `not` / `unknown`, or a missing chip, gives null, and a null card is never hidden. `keep`
is true only for a literal `true`, and malformed check rows are dropped. `ggLikeSplit` is the 🚩 display filter. When
it is OFF, every card stays and only `like` is counted. When it is ON, a card leaves ONLY when its verdict is `not`,
it is not served `keep: true` (it rang) and the fourth `keep` callback does not name it (the `?focus=` card opened from
an alert). Those kept ✗ cards are counted in `kept`, never in `hidden`. `unknown` cards and cards with no block stay in
place and are counted apart. Nothing is reordered. `ggLikeCount` is the toggle's live count (`gg_like` only), shown
before he taps. `ggLikeLabel` fills the served `label_n_text`. `ggLikeLine` builds the count line from the served
templates and drops every zero part. When every card is hidden, the line starts with the served `all_hidden_text`.
There is ONE localStorage key, `gg-like-only:board`: `'1'` is ON, and anything else or blocked storage is OFF. There
is no 👀 Watch filter.

`frontend/src/components/GgLike.tsx` prints served strings only:
- `GgLikeChip`: hover shows the served title.
- `GgLikeList`: the ✓ / ✗ / n/a rows, then the ⓘ info rows. Info rows are muted and never get the ✗ class.
- `GgLikeCard`: the list stays closed until the chip is tapped.
- `GgLikeToggle`: a `cm-phase-btn` showing the live count.
- `GgLikeHiddenLine`: the count line plus `show all`. It draws nothing while OFF.
- `GgLikeNote`: the note, then the separation and census sentences, then the per-check rows. It is mounted in a ⓘ fold
  body only.

`frontend/src/styles/ggLike.css` wraps everything on a 430 px phone. Mounting on the boards is done by the `fe-board`
and `fe-watch` packages.

Tests: `frontend/src/lib/ggLike.test.ts` and `frontend/src/components/GgLike.test.tsx`. They include NEGATIVE cases:
kept rows are never counted as hidden, `unknown` is never hidden, only `'1'` turns the filter ON, the component and lib
files type no served word, and a CSS wrap guard.

**2026-11-27 — refix: the hidden count no longer prints one card's number for another.** As first built,
`ggLikeSplit` keyed hidden cards by reason code but printed the FIRST card's label, so ✗ cards 23% / 51% / 16% under
the high read "3 23% under high". The served `reason` may now carry `count_label`, a per-code label with no card
number, and the split counts under it (key = code + label). When `count_label` is missing or blank, cards are grouped
by their exact served label, so a group only ever holds cards that were served the words it prints. The backend half
(`gg_like.py` serving `reason.count_label`, and its wording) is outside this package and not done here. Until it
ships, the line itemizes each distinct number separately. Tests: the `[refix]` cases in
`frontend/src/lib/ggLike.test.ts`.
