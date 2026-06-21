## 2024-06-03 - Adding ARIA labels to close buttons
**Learning:** Some custom drawer/modal components (like PriceAlertModal) use icon-only close buttons (`×`) without an explicit `aria-label`, making them inaccessible to screen readers.
**Action:** Always verify that "X" close buttons in custom modal implementations have `aria-label="Close"`.
