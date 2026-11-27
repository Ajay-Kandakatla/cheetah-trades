# 🧘 GG-like on the 🚩 board and the 🏁 Track record — frontend mounts (2026-11-27)

Ajay 2026-11-27: "find calmer and better setups.. Continue to track the runners we might evolve and find patterns in the
current runners too but I want to make sure we are finding similar setups to Gajjala".

Spec: `gglike/spec.md` §3.9, WP `fe-board`. Engine words and the frozen FE API are `lib/ggLike.ts` + `components/GgLike.tsx`
(WP `fe-core`). Display only, UNMEASURED: nothing rings, gates, sorts or changes list membership on the server.

## 2026-11-27 — what the board draws

- **Card chip.** Every 🚩 card whose read carries a served `gajjala.gg_like` block draws ONE chip (`GgLikeCard`) at the
  end of the pills row, beside the 💧 marker. The check list is closed until the chip is tapped, then opens on its own row
  under the pills. A card with no block draws exactly today's DOM.
- **Filter toggle.** In the controls row, before the ⓘ: the served `label_n_text` with the live count of cards reading
  GG-like (after the 💋 split), so the count is visible before the tap. Drawn only when the board serves `gg_like` and at
  least one card carries a parsed block. Remembered per device under the ONE key `gg-like-only:board`; default OFF.
- **What ON hides.** Only a ✗ card that is not kept. Kept = served `keep: true` (it rang, or its 🧠 push rang) or the
  `?focus=` name (opened from an alert). "Can't tell" cards and cards with no block stay. Nothing is reordered.
  The split runs right after the 💋 split and replaces `liveTiles`, so the card-watch layout, the 🚫 section splice, the
  🔝 divider, the ⤢ stepper and the focus scroll all read the drawn list. The room POST, the live poll, the counts line
  and the served tiles are not touched.
- **Count line.** While ON, `GgLikeHiddenLine` sits next to the 💋 line: hidden by reason, kept, can't tell, no check,
  and `show all` (which turns the filter OFF). When every card is hidden the line starts with the served
  `all_hidden_text`; the board's own empty note does not show (the tab is not empty).
- **Note.** `GgLikeNote` (note, separation sentence, census sentence, one row per check) mounts only inside the sub's ⓘ
  fold body — never above the cards.
- **🏁.** The served row chip (`days[].rows[].gg_like`) sits beside the 📶 chip in the Kind cell; its hover is the served
  title plus the served source words ("computed later …" when that is the source). A second closed `<details>` after the
  rule fold prints `gg_like_split`: summary = label, then title, every line in order, then the note. No block → no fold.

`lib/gajjala.ts` gained types only: `gg_like?: unknown` on `GgRead`, `GgBoard`, `GgTrRow`; `gg_like_split` on
`GgTrackRecord`.

Tests: `frontend/src/components/GajjalaBoard.gg_like.test.tsx` (chip / toggle / ON / push link in grid and card-watch /
all-hidden / fold note / 💋 compose / 🚫 header / 🏁 / 430 px and source guards, negatives in each group).

**2026-11-27 refix (T10).** While the 🧘 filter is ON, the line row and its served `show all` are always drawn — also
when nothing is hidden, kept, can't-tell or unchecked (e.g. a board of GG-like cards only). In that case the row holds
only `show all`; no count words are invented. The board passes `on` to `GgLikeHiddenLine`; without `on` an empty line
still draws nothing. Tests: `GgLike.test.tsx` (`[T10]` x2 + NEGATIVE), `GajjalaBoard.gg_like.test.tsx` ("ON with nothing
to hide [T10]" + NEGATIVE OFF).
