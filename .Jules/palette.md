## 2024-11-20 - Adding ARIA attributes to PriceAlertModal
**Learning:** Found an accessibility issue pattern specific to this app's components, where custom modals constructed using `createPortal` with a fixed-position container lack `role="dialog"` and `aria-modal="true"`.
**Action:** Audit other custom modals constructed with `createPortal` and `position: 'fixed'` to ensure they have proper ARIA attributes to support screen readers.
