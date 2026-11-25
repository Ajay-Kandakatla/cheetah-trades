# 👀 Gajjala's Watch — the view lives in the link (2026-11-16)

> **2026-11-25 — changed.** The link no longer carries `page=` (dropped on the first write); `per` and `show` are unchanged. See [watch_columns_scroll_2026_11_25.md](watch_columns_scroll_2026_11_25.md).

Ajay: "Can you make the board persist please... Like the 1 selection and the stock selection too.. So I can share with someone"

- The link carries the view: `per` = charts per screen (1 · 2 · 4 · 9), `show` = the names toggled on (comma list),
  `page` = the 1-based page (only without a pick, only past page 1). Every other param (`tab`, `focus`) is kept.
- This browser remembers it too: `ggw.layout` and `ggw.pick` in localStorage. A link wins over the browser; a link with
  `per` but no `show` is the whole view (the browser's pick is not mixed in).
- Junk is ignored: a bad `per` → the default 2, a bad `page` → page 1, a name not on the watch list drops out, and the
  board never comes up empty because of a link. Blocked storage (private window) still works from the link.
- Layout only — no rule, gate or number changes.
- Sharing: the 👀 Watch tab is owner-only today, so someone else opening the link sees "Shown to the account owner
  only". A read-only share view for other people = HIS CALL.

Code: `frontend/src/lib/gajjalaWatch.ts` (`GGW_URL`, `parseGgwPick`, `parseGgwPage`, `readGgwPick`, `saveGgwPick`,
`ggwViewParams`), `frontend/src/components/GajjalaWatchBoard.tsx`. Tests:
`frontend/src/components/GajjalaWatchBoard.link.test.tsx` (lib + board, NEGATIVES on junk, missing names, blocked storage,
kept params).
