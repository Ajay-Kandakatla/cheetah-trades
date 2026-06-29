## 2024-06-29 - Inconsistent ARIA Labels on Modals
**Learning:** Found an accessibility inconsistency where `PriceAlertModal.tsx` was missing `aria-label="Close"` on its close button, whereas almost all other modals (`MoatPeersModal.tsx`, `InstallToHomeScreen.tsx`, etc.) correctly implemented it.
**Action:** Add `aria-label="Close"` to `PriceAlertModal.tsx` to restore accessibility parity.
