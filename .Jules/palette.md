## 2024-07-04 - ARIA labels for icon-only modals
**Learning:** The `PriceAlertModal` and other similar modals often use a simple `×` character for the close button without an aria-label, which is completely opaque to screen readers.
**Action:** Added `aria-label="Close"` to the close button in `PriceAlertModal.tsx`. Always ensure icon-only close buttons in dialogs/modals have descriptive aria-labels.
