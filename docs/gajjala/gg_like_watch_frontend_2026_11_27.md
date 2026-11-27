# 🧘 GG-like calm check — 👀 Watch and 📅 roster mounts (2026-11-27)

Ajay 2026-11-27: "find calmer and better setups.. Continue to track the runners we might evolve and find patterns in the
current runners too but I want to make sure we are finding similar setups to Gajjala".
Spec: `scratchpad/gglike/spec.md` §3.9, work package `fe-watch`. Scope 🟡: display only. Nothing rings, gates, sorts,
reorders or hides. UNMEASURED.

**2026-11-27 — chip and list only, nothing hidden.** The strict parsers now carry the served keys:
- `lib/gajjalaWatch.ts`: each `tags.setups[]` item keeps its served `gg_like` (through `lib/ggLike.parseGgLike`). The
  key is set only when the block parses, so junk, a null or an older server leaves the item exactly as before.
  `parseRowOrg` keeps the setup KEY of the served setup chip as `org.setup_key`, again only when served.
  `ggwTileGgLike(row)` picks the tile's block: the setup chip's key, else 🎾 when carded, else the first carded. It always
  returns THAT setup's own block, or null. It never borrows another setup's block and never computes one.
- `lib/ggwRunRoster.ts`: a roster row keeps its served `gg_like` chip (only when it parses), and the record keeps the
  served `gg_like_text` counts line (null when absent).

Mounts:
- 👀 compact tile: the chip (a `<span>`, hover = the served title) sits right after the setup chip. The ✓ / ✗ / n/a rows
  sit inside the ⋯ drawer (`ggw-gglike-SYM`).
- 📅 roster row: the chip (a `<span>`) sits right after the seat chip. There is no filter on the roster.
- 📅 record: the served counts line prints only inside the existing ⓘ fold, right after the summary line, and only once
  the fold has been opened and read.

There is NO toggle, no hidden line, no `hidden` attribute and no localStorage key on the Watch. Every A+ push lands
there, so 🧘 never hides a Watch tile (critique C1, C7). `GajjalaWatchBoard.tsx` and `GajjalaWatchLayout.tsx` are not
edited.

Tests: `frontend/src/components/GajjalaWatchBoard.gg_like.test.tsx` renders the real board and the roster. It checks
that the chip follows the setup chip and is that setup's block, with the 🎾 fallback, and that the list sits in the
drawer. NEGATIVE cases:
- `tags` null, no block or a junk block draws nothing new on the tile.
- A chip that names an uncarded setup draws no 🧘 chip.
- A Watch of ✗ rows with `gg-like-only:watch` and `gg-like-only:board` set by hand shows the same tiles, pager chips and
  section counts as a Watch with the blocks stripped, on phone and desktop. Neither key is read or written.
- A `?focus=` link on a ✗ row is shown, outlined and scrolled to once.
- The roster keeps the same rows as without the blocks, and the 📅 line is not in the DOM while the fold is closed.
- 430 px source guards: the tile head, the drawer row and the roster row wrap with `min-width: 0`, the chip wraps
  anywhere, and a pre-fix sheet fails the same matchers. The new mount lines carry no inline width, no storage key and no
  🧘 words.
