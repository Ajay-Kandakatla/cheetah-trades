## 2024-07-08 - Close Button Accessibility
**Learning:** Found multiple instances where the "×" (close) button was missing an `aria-label`, making it completely inaccessible and unintelligible for screen readers.
**Action:** Always ensure that icon-only buttons (like `×` for close) include an `aria-label` (e.g., `aria-label="Close"`) to provide necessary context for screen reader users.
