## 2024-06-06 - Missing ARIA Labels on Icon-Only Buttons
**Learning:** Found a pattern of icon-only buttons (like in Todos and Watchlist) relying solely on the `title` attribute for accessibility context.
**Action:** Always verify that icon-only buttons include an `aria-label` attribute, as relying only on `title` is insufficient for some screen readers and keyboard users.
