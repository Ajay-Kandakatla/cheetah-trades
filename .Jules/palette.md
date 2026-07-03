## 2024-07-24 - Missing ARIA labels on "×" close buttons
**Learning:** Icon-only close buttons (typically represented by a "×" character) often lack `aria-label` attributes. This is a common accessibility issue for screen readers.
**Action:** When inspecting modals, drawers, or overlay components, proactively check that icon-only buttons have an appropriate `aria-label` (e.g., `aria-label="Close"`).
