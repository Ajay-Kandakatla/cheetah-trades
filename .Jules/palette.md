## 2024-05-21 - Added aria-label to PriceAlertModal Close Button
**Learning:** Found an icon-only button (a close button using only the "×" symbol) that was missing an `aria-label` attribute in the `PriceAlertModal` component. This was causing a minor accessibility issue for screen reader users.
**Action:** When creating close buttons, ensure that icon-only buttons include an `aria-label="Close"` attribute.
